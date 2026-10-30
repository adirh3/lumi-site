"""Creates the sample projects Lumi works in for the site's recordings, in <demo_dir> (replaced):
  checkout-api  the hero loop: a small, real ASP.NET Core minimal API whose checkout got slower after a commit
                swapped one cached batch price lookup for a live lookup per cart item, with two weeks of exported
                request logs and the deploy log in logs/ (not committed)
  weather-cli   the "Hand it a task" screenshot: a small .NET console app that really crashes on an empty
                hourly forecast (`weather forecast Reykjavik --hourly`), with xUnit tests, on branch fix/empty-hourly

usage: python tools/capture/make_samples.py <demo_dir>
Use a short, neutral folder outside your user profile, such as a demo folder at the root of a data drive: Lumi's
steps can show paths inside it, and they end up in the recordings. Needs git, the .NET 10 SDK and numpy.
"""
import csv
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

if len(sys.argv) < 2:
    sys.exit(__doc__)
DEMO = Path(sys.argv[1]).resolve()
REPO = DEMO / "checkout-api"
WEATHER = DEMO / "weather-cli"
UTC = timezone.utc

PROGRAM_V1 = """using Checkout.Api.Carts;
using Checkout.Api.Checkout;
using Checkout.Api.Pricing;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddHttpClient<PriceClient>(client =>
    client.BaseAddress = new Uri(builder.Configuration["Pricing:BaseUrl"] ?? "http://pricing.internal/"));
builder.Services.AddMemoryCache();
builder.Services.AddScoped<CatalogPrices>();
builder.Services.AddSingleton<CartStore>();
builder.Services.AddScoped<CheckoutService>();

var app = builder.Build();

app.MapGet("/products", (CartStore store) => store.Products());
app.MapGet("/search", (string q, CartStore store) => store.Search(q));
app.MapGet("/cart/{id}", (string id, CartStore store) => store.Get(id));
app.MapPost("/checkout", async (CheckoutRequest request, CheckoutService checkout, CancellationToken ct) =>
    Results.Ok(await checkout.QuoteAsync(request.CartId, ct)));
app.MapGet("/orders", (CartStore store) => store.Orders(page: 1));

app.Run();

public sealed record CheckoutRequest(string CartId);
"""

PROGRAM_V2 = PROGRAM_V1.replace(
    'app.MapGet("/orders", (CartStore store) => store.Orders(page: 1));',
    'app.MapGet("/orders", (int? page, CartStore store) => store.Orders(page ?? 1));')

PROGRAM_V7 = PROGRAM_V2.replace(
    """app.MapPost("/checkout", async (CheckoutRequest request, CheckoutService checkout, CancellationToken ct) =>
    Results.Ok(await checkout.QuoteAsync(request.CartId, ct)));""",
    """app.MapPost("/checkout", async (CheckoutRequest request, CartStore store, CheckoutService checkout, CancellationToken ct) =>
    store.Get(request.CartId).Items.Count == 0
        ? Results.BadRequest("The cart is empty.")
        : Results.Ok(await checkout.QuoteAsync(request.CartId, ct)));""")

CARTS_V1 = """namespace Checkout.Api.Carts;

public sealed record Product(string Sku, string Name, decimal ListPrice);

public sealed record CartItem(string Sku, int Quantity);

public sealed record Cart(string Id, IReadOnlyList<CartItem> Items);

public sealed record Order(string Id, DateTime PlacedAt, decimal Total);

public sealed class CartStore
{
    private readonly Dictionary<string, Cart> _carts = new();
    private readonly List<Order> _orders = new();
    private readonly List<Product> _products =
    [
        new("SKU-1001", "Pour-over kettle", 49m),
        new("SKU-1002", "Ceramic dripper", 24m),
        new("SKU-1003", "Paper filters, 100", 6m),
        new("SKU-1004", "Burr grinder", 129m),
        new("SKU-1005", "Glass server", 32m),
    ];

    public IReadOnlyList<Product> Products() => _products;

    public IEnumerable<Product> Search(string q) =>
        _products.Where(p => p.Name.Contains(q, StringComparison.OrdinalIgnoreCase));

    public Cart Get(string id) => _carts.TryGetValue(id, out var cart) ? cart : new Cart(id, []);

    public IReadOnlyList<Order> Orders(int page, int pageSize = 20) =>
        _orders.OrderByDescending(o => o.PlacedAt).Skip((page - 1) * pageSize).Take(pageSize).ToList();
}
"""

CARTS_V4 = CARTS_V1.replace(
    "public sealed record CartItem(string Sku, int Quantity);",
    """public sealed record CartItem(string Sku, int Quantity)
{
    public int Quantity { get; } = Quantity is >= 1 and <= 99
        ? Quantity
        : throw new ArgumentOutOfRangeException(nameof(Quantity), "Quantity must be between 1 and 99.");
}""")

CARTS_V6 = CARTS_V4.replace(
    """    public IEnumerable<Product> Search(string q) =>
        _products.Where(p => p.Name.Contains(q, StringComparison.OrdinalIgnoreCase));""",
    """    public IEnumerable<Product> Search(string q) => _products
        .Where(p => p.Sku.Equals(q, StringComparison.OrdinalIgnoreCase)
            || p.Name.Contains(q, StringComparison.OrdinalIgnoreCase))
        .OrderByDescending(p => p.Sku.Equals(q, StringComparison.OrdinalIgnoreCase));""")

PRICE_CLIENT = """using System.Net.Http.Json;

namespace Checkout.Api.Pricing;

public sealed class PriceClient(HttpClient http)
{
    /// <summary>The live price of one SKU, including active promotions.</summary>
    public async Task<decimal> GetPriceAsync(string sku, CancellationToken ct)
    {
        var price = await http.GetFromJsonAsync<Price>($"prices/{sku}", ct);
        return price?.Amount ?? throw new InvalidOperationException($"No price for {sku}.");
    }

    /// <summary>Live prices for many SKUs in one request, including active promotions.</summary>
    public async Task<IReadOnlyDictionary<string, decimal>> GetPricesAsync(IEnumerable<string> skus, CancellationToken ct)
    {
        using var response = await http.PostAsJsonAsync("prices/batch", skus, ct);
        response.EnsureSuccessStatusCode();
        var prices = await response.Content.ReadFromJsonAsync<Price[]>(ct) ?? [];
        return prices.ToDictionary(p => p.Sku, p => p.Amount);
    }

    private sealed record Price(string Sku, decimal Amount);
}
"""

CATALOG_PRICES = """using Microsoft.Extensions.Caching.Memory;

namespace Checkout.Api.Pricing;

/// <summary>Catalog prices for a set of SKUs, cached for five minutes.</summary>
public sealed class CatalogPrices(PriceClient prices, IMemoryCache cache)
{
    public async Task<IReadOnlyDictionary<string, decimal>> GetAsync(IReadOnlyCollection<string> skus, CancellationToken ct)
    {
        var key = "prices:" + string.Join(',', skus.Order());
        var cached = await cache.GetOrCreateAsync(key, entry =>
        {
            entry.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(5);
            return prices.GetPricesAsync(skus, ct);
        });
        return cached ?? new Dictionary<string, decimal>();
    }
}
"""

QUOTES = """namespace Checkout.Api.Checkout;

public sealed record QuoteLine(string Sku, int Quantity, decimal UnitPrice)
{
    public decimal Total => UnitPrice * Quantity;
}

public sealed record Quote(string CartId, IReadOnlyList<QuoteLine> Lines, decimal Total);
"""

CHECKOUT_V1 = """using Checkout.Api.Carts;
using Checkout.Api.Pricing;

namespace Checkout.Api.Checkout;

public sealed class CheckoutService(CartStore carts, PriceClient prices)
{
    public async Task<Quote> QuoteAsync(string cartId, CancellationToken ct)
    {
        var cart = carts.Get(cartId);
        var unitPrices = await prices.GetPricesAsync(cart.Items.Select(i => i.Sku), ct);
        var lines = cart.Items.Select(i => new QuoteLine(i.Sku, i.Quantity, unitPrices[i.Sku])).ToList();
        return new Quote(cartId, lines, lines.Sum(l => l.Total));
    }
}
"""

CHECKOUT_V3 = """using Checkout.Api.Carts;
using Checkout.Api.Pricing;

namespace Checkout.Api.Checkout;

public sealed class CheckoutService(CartStore carts, CatalogPrices catalog)
{
    public async Task<Quote> QuoteAsync(string cartId, CancellationToken ct)
    {
        var cart = carts.Get(cartId);
        var unitPrices = await catalog.GetAsync(cart.Items.Select(i => i.Sku).ToArray(), ct);
        var lines = cart.Items.Select(i => new QuoteLine(i.Sku, i.Quantity, unitPrices[i.Sku])).ToList();
        return new Quote(cartId, lines, lines.Sum(l => l.Total));
    }
}
"""

CHECKOUT_V5 = """using Checkout.Api.Carts;
using Checkout.Api.Pricing;

namespace Checkout.Api.Checkout;

public sealed class CheckoutService(CartStore carts, PriceClient prices)
{
    public async Task<Quote> QuoteAsync(string cartId, CancellationToken ct)
    {
        var cart = carts.Get(cartId);
        var lines = new List<QuoteLine>(cart.Items.Count);

        // Live prices, so a promotion applies the moment it starts.
        foreach (var item in cart.Items)
        {
            var price = await prices.GetPriceAsync(item.Sku, ct);
            lines.Add(new QuoteLine(item.Sku, item.Quantity, price));
        }

        return new Quote(cartId, lines, lines.Sum(l => l.Total));
    }
}
"""

BASE_FILES = {
    "global.json": """{
  "sdk": { "version": "10.0.114", "rollForward": "latestFeature" }
}
""",
    ".gitignore": "bin/\nobj/\nlogs/\n",
    "README.md": """# checkout-api

Cart, checkout and order history for the shop: an ASP.NET Core minimal API.

Prices come from the pricing service (`Pricing:BaseUrl`). Production request logs and the deploy
log are exported to `logs/`, which is not committed.
""",
    "src/Checkout.Api/Checkout.Api.csproj": """<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
</Project>
""",
    "src/Checkout.Api/appsettings.json": """{
  "Pricing": { "BaseUrl": "http://pricing.internal/" },
  "Logging": { "LogLevel": { "Default": "Information" } }
}
""",
    "src/Checkout.Api/Program.cs": PROGRAM_V1,
    "src/Checkout.Api/Carts/CartStore.cs": CARTS_V1,
    "src/Checkout.Api/Pricing/PriceClient.cs": PRICE_CLIENT,
    "src/Checkout.Api/Checkout/Quote.cs": QUOTES,
    "src/Checkout.Api/Checkout/CheckoutService.cs": CHECKOUT_V1,
}

# (when, author, message, {path: text or None to delete})
COMMITS = [
    ("2026-10-09T09:14:00Z", "Alex", "Checkout service with cart, product and order endpoints", BASE_FILES),
    ("2026-10-12T13:30:00Z", "Priya", "Add order history paging", {"src/Checkout.Api/Program.cs": PROGRAM_V2}),
    ("2026-10-13T10:41:00Z", "Sam", "Cache catalog prices for five minutes", {
        "src/Checkout.Api/Pricing/CatalogPrices.cs": CATALOG_PRICES,
        "src/Checkout.Api/Checkout/CheckoutService.cs": CHECKOUT_V3}),
    ("2026-10-16T15:22:00Z", "Alex", "Validate cart quantities", {"src/Checkout.Api/Carts/CartStore.cs": CARTS_V4}),
    ("2026-10-20T15:45:00Z", "Sam", "Use live prices at checkout so promotions apply instantly", {
        "src/Checkout.Api/Checkout/CheckoutService.cs": CHECKOUT_V5}),
    ("2026-10-22T12:05:00Z", "Priya", "Improve search ranking for exact SKU matches", {
        "src/Checkout.Api/Carts/CartStore.cs": CARTS_V6}),
    ("2026-10-25T16:30:00Z", "Alex", "Return 400 for empty carts", {"src/Checkout.Api/Program.cs": PROGRAM_V7}),
]

# Deploys: (commit index, version, deployed at, by)
DEPLOYS = [
    (2, "1.7.0", "2026-10-13T13:02:00Z", "Sam"),
    (3, "1.7.1", "2026-10-19T08:05:00Z", "Alex"),
    (4, "1.8.0", "2026-10-21T07:20:00Z", "Sam"),
    (5, "1.8.1", "2026-10-23T11:40:00Z", "Priya"),
    (6, "1.8.2", "2026-10-26T08:10:00Z", "Alex"),
]
REGRESSION = datetime(2026, 10, 21, 7, 20, tzinfo=UTC)
EMAILS = {"Alex": "alex@example.com", "Priya": "priya@example.com", "Sam": "sam@example.com"}


def git(*args, env=None):
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True,
                          env={**os.environ, **(env or {})}).stdout.strip()


def make_repo():
    if DEMO.exists():
        shutil.rmtree(DEMO, onerror=lambda func, path, _: (os.chmod(path, stat.S_IWRITE), func(path)))
    REPO.mkdir(parents=True)
    git("init", "-q", "-b", "main")
    git("config", "commit.gpgsign", "false")
    shas = []
    for when, author, message, files in COMMITS:
        for rel, text in files.items():
            path = REPO / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        git("add", "-A")
        env = {"GIT_AUTHOR_NAME": author, "GIT_AUTHOR_EMAIL": EMAILS[author], "GIT_AUTHOR_DATE": when,
               "GIT_COMMITTER_NAME": author, "GIT_COMMITTER_EMAIL": EMAILS[author], "GIT_COMMITTER_DATE": when}
        git("commit", "-q", "-m", message, env=env)
        shas.append(git("rev-parse", "--short=7", "HEAD"))
    git("config", "user.name", "Alex")
    git("config", "user.email", EMAILS["Alex"])
    return shas


def make_logs(shas):
    logs = REPO / "logs"
    logs.mkdir()
    with open(logs / "deploys.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["deployed_at", "version", "commit", "deployed_by"])
        for index, version, when, by in DEPLOYS:
            w.writerow([when, version, shas[index], by])

    rng = np.random.default_rng(20261021)
    # Requests per weekday; weekends get 70%.
    volume = {"/products": 1400, "/search": 900, "/cart/{id}": 700, "/checkout": 420, "/orders": 300}
    method = {"/checkout": "POST"}
    hour_weight = np.array([0.25, 0.15, 0.1, 0.1, 0.15, 0.3, 0.6, 1.0, 1.3, 1.4, 1.4, 1.35,
                            1.3, 1.25, 1.2, 1.2, 1.3, 1.5, 1.7, 1.8, 1.6, 1.2, 0.8, 0.45])
    hour_weight = hour_weight / hour_weight.sum()
    rows = []
    start = datetime(2026, 10, 15, tzinfo=UTC)
    for day in range(14):
        date = start + timedelta(days=day)
        scale = 0.7 if date.weekday() >= 5 else 1.0
        for endpoint, per_day in volume.items():
            n = int(per_day * scale * rng.uniform(0.94, 1.06))
            hours = rng.choice(24, size=n, p=hour_weight)
            seconds = hours * 3600 + rng.uniform(0, 3600, size=n)
            stamps = [date + timedelta(seconds=float(s)) for s in np.sort(seconds)]
            items = np.zeros(n, dtype=int)
            if endpoint in ("/checkout", "/cart/{id}"):
                items = np.minimum(1 + rng.negative_binomial(2, 0.33, size=n), 24)
            if endpoint == "/products":
                ms = rng.lognormal(np.log(42), 0.32, n)
            elif endpoint == "/search":
                ms = rng.lognormal(np.log(78), 0.3, n)
            elif endpoint == "/cart/{id}":
                ms = rng.lognormal(np.log(31), 0.28, n) + items * 0.6
            elif endpoint == "/orders":
                ms = rng.lognormal(np.log(57), 0.3, n)
            else:
                ms = np.empty(n)
                for i, (stamp, count) in enumerate(zip(stamps, items)):
                    if stamp < REGRESSION:  # one cached batch lookup
                        miss = rng.random() < 0.15
                        ms[i] = rng.lognormal(np.log(138), 0.19) + count * 1.4 + (rng.lognormal(np.log(34), 0.3) if miss else 1.5)
                    else:                   # a live price call per item, one after another
                        ms[i] = rng.lognormal(np.log(116), 0.19) + rng.lognormal(np.log(30), 0.4, count).sum()
            status = np.where(rng.random(n) < 0.0012, 500, 200)
            for stamp, duration, code, count in zip(stamps, ms, status, items):
                rows.append((stamp, endpoint, method.get(endpoint, "GET"), int(code), int(round(duration)),
                             int(count) if count else ""))
    rows.sort(key=lambda r: r[0])
    with open(logs / "requests.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "method", "endpoint", "status", "duration_ms", "cart_items"])
        for stamp, endpoint, verb, code, duration, count in rows:
            w.writerow([stamp.strftime("%Y-%m-%dT%H:%M:%S.") + f"{stamp.microsecond // 1000:03d}Z",
                        verb, endpoint, code, duration, count])
    return rows


WEATHER_FILES = {
    "global.json": """{
  "sdk": { "version": "10.0.114", "rollForward": "latestFeature" }
}
""",
    "README.md": """# weather-cli

A small command-line weather client.

```sh
weather forecast Lisbon --hourly
```
""",
    ".gitignore": "bin/\nobj/\n",
    "src/WeatherCli/WeatherCli.csproj": """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net10.0</TargetFramework>
    <AssemblyName>weather</AssemblyName>
    <RootNamespace>WeatherCli</RootNamespace>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
</Project>
""",
    "src/WeatherCli/Program.cs": """using WeatherCli.Forecast;

if (args.Length < 2 || args[0] != "forecast")
{
    Console.WriteLine("Usage: weather forecast <city> [--hourly]");
    return 1;
}

var forecast = await new ForecastClient().GetAsync(args[1]);
Console.WriteLine(args.Contains("--hourly")
    ? HourlyFormatter.Format(forecast)
    : $"{forecast.City}: {forecast.Summary}");
return 0;
""",
    "src/WeatherCli/Forecast/Forecast.cs": """namespace WeatherCli.Forecast;

public sealed record HourlyEntry(DateTime Time, double Temperature, string Summary);

public sealed record WeatherForecast(string City, string Summary, IReadOnlyList<HourlyEntry> Hourly);
""",
    "src/WeatherCli/Forecast/ForecastClient.cs": """namespace WeatherCli.Forecast;

/// <summary>Reads forecasts from the bundled sample data. The real API can return no hourly entries.</summary>
public sealed class ForecastClient
{
    public Task<WeatherForecast> GetAsync(string city)
    {
        var start = DateTime.Today.AddHours(DateTime.Now.Hour);
        var hourly = city.Equals("Reykjavik", StringComparison.OrdinalIgnoreCase)
            ? []
            : Enumerable.Range(0, 24)
                .Select(h => new HourlyEntry(start.AddHours(h), 18 + 4 * Math.Sin(h / 4.0), h < 12 ? "Sunny" : "Clear"))
                .ToList();
        return Task.FromResult(new WeatherForecast(city, "Mild and mostly sunny", hourly));
    }
}
""",
    "src/WeatherCli/Forecast/HourlyFormatter.cs": """namespace WeatherCli.Forecast;

public static class HourlyFormatter
{
    public static string Format(WeatherForecast forecast, int hours = 12)
    {
        var first = forecast.Hourly[0];
        var lines = forecast.Hourly
            .Take(hours)
            .Select(h => $"{h.Time:HH:mm}  {h.Temperature,5:0.0}°  {h.Summary}");

        return $"{forecast.City}, from {first.Time:ddd HH:mm}\\n" + string.Join('\\n', lines);
    }
}
""",
    "tests/WeatherCli.Tests/WeatherCli.Tests.csproj": """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <IsPackable>false</IsPackable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.14.1" />
    <PackageReference Include="xunit" Version="2.9.3" />
    <PackageReference Include="xunit.runner.visualstudio" Version="3.1.4" />
  </ItemGroup>
  <ItemGroup>
    <Using Include="Xunit" />
  </ItemGroup>
  <ItemGroup>
    <ProjectReference Include="..\\..\\src\\WeatherCli\\WeatherCli.csproj" />
  </ItemGroup>
</Project>
""",
    "tests/WeatherCli.Tests/HourlyFormatterTests.cs": """using WeatherCli.Forecast;

namespace WeatherCli.Tests;

public class HourlyFormatterTests
{
    private static WeatherForecast Lisbon(int hours) => new(
        "Lisbon",
        "Sunny",
        Enumerable.Range(0, hours)
            .Select(h => new HourlyEntry(new DateTime(2026, 11, 5, 9, 0, 0).AddHours(h), 20, "Sunny"))
            .ToList());

    [Fact]
    public void Format_ShowsTheRequestedHours()
    {
        var text = HourlyFormatter.Format(Lisbon(24), hours: 6);

        Assert.Equal(7, text.Split('\\n').Length);
    }

    [Fact]
    public void Format_StartsWithTheCity()
    {
        var text = HourlyFormatter.Format(Lisbon(3));

        Assert.StartsWith("Lisbon, from", text);
    }
}
""",
}


def make_weather():
    def run(*args):
        return subprocess.run(args, cwd=WEATHER, capture_output=True, text=True)

    for rel, text in WEATHER_FILES.items():
        path = WEATHER / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    run("dotnet", "new", "sln", "-n", "WeatherCli", "--format", "slnx")
    run("dotnet", "sln", "WeatherCli.slnx", "add", "src/WeatherCli/WeatherCli.csproj", "tests/WeatherCli.Tests/WeatherCli.Tests.csproj")
    for args in (("init", "-q", "-b", "main"), ("config", "user.name", "Alex"), ("config", "user.email", EMAILS["Alex"]),
                 ("config", "commit.gpgsign", "false"), ("add", "-A"), ("commit", "-q", "-m", "Hourly forecast output"),
                 ("checkout", "-q", "-b", "fix/empty-hourly")):
        run("git", *args).check_returncode()
    run("dotnet", "build", "WeatherCli.slnx", "-v:q", "-nologo")
    tests = run("dotnet", "test", "WeatherCli.slnx", "--nologo", "--no-build").stdout.strip().splitlines()
    crash = run("dotnet", "run", "--project", "src/WeatherCli", "--no-build", "--", "forecast", "Reykjavik", "--hourly")
    print("weather-cli tests:", tests[-1] if tests else "didn't run")
    print("weather-cli crash reproduces:", "ArgumentOutOfRangeException" in crash.stderr + crash.stdout)
    print(run("git", "status", "--short", "--branch").stdout.strip())


def main():
    shas = make_repo()
    rows = make_logs(shas)
    print("commits:", " ".join(shas))
    print("rows:", len(rows), "size:", round((REPO / "logs/requests.csv").stat().st_size / 1e6, 2), "MB")
    by_day = {}
    for stamp, endpoint, _, _, duration, _ in rows:
        by_day.setdefault((stamp.date(), endpoint), []).append(duration)
    for endpoint in ("/checkout", "/products"):
        p95 = [int(np.percentile(by_day[(d, e)], 95)) for (d, e) in sorted(by_day) if e == endpoint]
        print(endpoint, "daily p95:", p95)
    build = subprocess.run(["dotnet", "build", "src/Checkout.Api", "-v:q", "-nologo"], cwd=REPO,
                           capture_output=True, text=True)
    print("build:", "ok" if build.returncode == 0 else build.stdout[-1500:])
    for d in ("src/Checkout.Api/bin", "src/Checkout.Api/obj"):
        shutil.rmtree(REPO / d, ignore_errors=True)
    print(git("status", "--short", "--branch"))
    print(git("log", "--oneline", "--format=%h %ad %an %s", "--date=short"))
    make_weather()


if __name__ == "__main__":
    main()
