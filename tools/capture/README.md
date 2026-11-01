# Capturing Lumi for the site

The hero loop and the feature screenshots come from a real Debug Lumi in an isolated, seeded profile. Capture again
when Lumi's UI changes visibly, so the page shows the release people download. Windows only. Allow about an hour
for the hero loop (both themes); the screenshots take less.

## Rules

- **Isolated profile, sample data.** Launch Lumi with `launch.ps1`, which points `LUMI_APPDATA_DIR` at a profile
  seeded by `seed_profile.py`; never Adir's real profile. The user is "Alex", and nothing real may appear: no real
  chats, names, accounts, paths or machine names.
- **A neutral sample folder** outside your user profile, such as a `demo` folder at the root of a data drive: Lumi's
  steps can show paths inside it.
- **Only your own processes.** Never stop other Lumi windows (Adir's Release app, other chats' Debug builds). Stop
  yours by PID when you're done.
- **A Debug build** from a worktree of `adirh3/Lumi` at the commit being released, never the main checkout.
- **Window size:** Lumi's client area is 1980×1290 on a 100% (96 DPI) monitor, with the profile's UI scale of 150%.
  `launch.ps1` and `stage_window.py` set it, and `stage_window.py` warns when it's off.
- **Debug chrome:** hide the Debug overlay (`set_property #AgentDebugMap IsVisible false`). Debug builds also show
  the worktree's folder name at the window's top-left; `make_loop.py` paints over it and the screenshot crops leave
  it out.
- Keep working files outside the repo (a take is gigabytes), and delete them, the samples and the profiles when done.

The commands below name Avalonia MCP tools (`set_property`, `click_control`, `scroll`, `input_text`, …; a global
connector in Lumi) with your Lumi's PID, and Lumi's UI Automation tools (`ui_find`, `ui_do`) with its window,
`hwnd:0x…`. The transcript's scroller is `#PART_TranscriptScroll`; `#Transcript` resolves to an empty inner scroller.

## Set up

```powershell
$demo = '<sample folder>'                                   # neutral, outside your user profile
python tools/capture/make_samples.py $demo                  # checkout-api and weather-cli, with their git history
python tools/capture/seed_profile.py $profile $demo         # add --light for the light theme
tools/capture/launch.ps1 -Exe <worktree>\src\Lumi\bin\Debug\<tfm>\win-x64\Lumi.exe -Profile $profile
```

`launch.ps1` prints `PID=… HWND=…` (and the `hwnd:0x…` form), which the other tools take. Each theme is its own
profile and its own Lumi. A real run can change its sample (the bug fix edits weather-cli), so close Lumi and run
`make_samples.py` again before the next real run.

## The hero loop

The hero plays a real run cut into a seamless 30-second loop: it opens on the answer's chart (that frame is also the
still and the social image), scrolls to the diagram and the checklist, dissolves to a new chat, types the question on
the launchpad, and plays the work and the answer sped up. Dark and light are two runs of the same question.

1. **Prepare a real new chat:** `set_property #Composer ProjectName "checkout-api"`. That is what the composer's
   project picker does: the composer shows the project and branch chips and the sidebar switches to the project.
   Lumi opens on the launchpad ("Good afternoon, Alex"); don't create the chat any other way.
2. **Record the main take.** Stage the window, start the recorder in the background, type, send:
   ```powershell
   python tools/capture/stage_window.py $hwnd sliver
   python tools/capture/record_window.py $hwnd $take $take.stop 420 30      # background; stops when $take.stop exists
   tools/capture/type_chars.ps1 -Hwnd $hwnd -Text $prompt                    # ~2 s after the recorder starts
   ```
   Then send with `input_text #Composer`, the same text and `pressEnter: true` (it replaces the text with itself, so
   nothing visibly changes). The prompt:
   > Checkout has been slow since last week. Use logs/ and the git history to find out why. Chart the daily latency, diagram the slow path and give me a fix checklist.

   Lumi names the chat itself. Poll `get_control_properties #Composer IsBusy` until it's false, wait about 12 s for
   the follow-up suggestions, then create `$take.stop`. Check the answer has a chart, a diagram and a checklist; if
   not, record again.
3. **Find the framings** with `scroll #PART_TranscriptScroll y=<offset>` and `snap_window.py $hwnd x.png`: the chart
   frame (the first frame and the social image) shows the key finding and the whole chart (about `y=120`); the
   diagram frame shows the whole diagram above the suggestions (about 600–700). Note the bottom offset (`scrollMax`).
4. **Record the gestures clip** on the finished answer: `scroll #PART_TranscriptScroll edge=bottom`, start a second
   recorder, then three wheel gestures (2.4 wheel units per pixel; positive scrolls up):
   ```powershell
   python tools/capture/wheel.py $hwnd 1925 600  <2.4 × (bottom − chart)>   1.2   # A: bottom → chart
   python tools/capture/wheel.py $hwnd 1925 600 -<2.4 × (diagram − chart)>  1.1   # B1: chart → diagram
   python tools/capture/wheel.py $hwnd 1925 600 -<2.4 × (bottom − diagram)> 1.1   # B2: diagram → bottom
   ```
   After each one, read `scroll #PART_TranscriptScroll` (no other arguments): Lumi queues wheel input from a window
   that isn't active until something wakes its UI thread, and the read does. Read again after ~1.5 s to confirm the
   offset, hold ~2 s, then the next gesture. Stop the recorder ~2 s after B2.
5. **Timestamps.** From `<profile>\Lumi\lumi.db` (SQLite, read-only), table `messages`: the user message's
   `timestamp` and the final assistant message's (`role = 'assistant'`, a body without `"isProgress": true`). Then:
   ```powershell
   python tools/capture/analyze_take.py $take <user_ms> <final_answer_ms>     # prints send_ms, answer_ms, done_ms
   python tools/capture/make_loop.py $take $loop <send_ms> <answer_ms> <done_ms> --gestures=$gestures --gesture-speed=1.6 --preview
   ```
   Look at the `preview-*.png` frames (rest, diagram, bottom, empty, typed, streaming, done), then run it again
   without `--preview` to write the frames. The first and last frames must be identical (it loops).
6. **Encode, stills and the social image:**
   ```powershell
   tools/capture/encode.ps1 -Frames $loopDark -Theme dark      # and light
   python tools/capture/build_stills.py $loopDark $loopLight <lumi repo>
   ```
   Update the hero's `alt` text in `index.html` if the answers' facts changed (it describes both themes), then
   follow AGENTS.md: validate, scan with `--ocr`, commit, deploy.
   For a social-image copy change without new captures, use
   `python tools/capture/build_stills.py --og-only <lumi repo>`. It reuses the existing dark hero still, leaves the
   hero media untouched and keeps the social image at 1280x640. Update the image alt text in `index.html` to match.
   GitHub social previews are separate uploads: re-upload the image there if it was used previously.
7. **Clean up:** stop your Lumi by PID (`stage_window.py $hwnd park` first if you keep it), and delete the takes,
   loops, samples and profiles.

## The screenshots

Capture each one in both themes with `python tools/capture/snap_window.py $hwnd <file>.png`, then
`python tools/images.py shot <name> <dark.png> <light.png>` writes the page's sizes (its `SHOTS` table has each
crop; `--crop=x0,y0,x1,y1` overrides it). Update the image's `alt` text in `index.html` when what it shows changes.

| Image | Section of the page | How to get there |
|---|---|---|
| `work` | Hand it a task. See every step. | A real run, below |
| `files` | Your files, documents and the web. | On the launchpad, open "October expenses from receipts" (`ui_do` click on it), then `scroll #PART_TranscriptScroll edge=top` |
| `customize` | Shape it around how you work. | `click_control #NavCustomize`, then `click_control #CustomizeSkillsTab` |
| `phone` | Check in from your phone. | The mobile app's design preview, below |
| `accounts` | Works with the AI you already have. | `click_control #NavSettings`, `set_property #SettingsPagesList SelectedIndex 6` (AI & Models), `click_control #AddAiAccountButton`; close it afterwards with `set_property #EasyConnectDialog IsDialogOpen false` |

**work:** in a new chat in weather-cli (`set_property #Composer ProjectName "weather-cli"`), send with
`input_text #Composer` and `pressEnter: true`:

> `weather forecast Reykjavik --hourly` crashes when the API returns no hourly data. Find the cause, fix it, and add a regression test.

When `#Composer`'s `IsBusy` is false, open its steps (`set_property StrataTurnSummary[0] IsExpanded true`), scroll to
the top (`scroll #PART_TranscriptScroll edge=top`) and capture. The first screen should show the request and then the
work opened up: reasoning, the skill used, a short plan and groups of finished steps.

**phone:** the Android app's interface, from its design preview with synthetic data. Build
`src\Lumi.Mobile.Desktop\Lumi.Mobile.Desktop.csproj` in the worktree, then run it with two new empty folders:

```powershell
$env:LUMI_APPDATA_DIR = '<empty folder>'; $env:LUMI_MOBILE_DATA_DIR = '<another empty folder>'
<worktree>\src\Lumi.Mobile.Desktop\bin\Debug\net11.0\Lumi.Mobile.Desktop.exe --design-preview --device "Pixel 8 Pro"
```

Drive it with Windows UI Automation (`ui_do` on "Lumi Mobile - design preview"; background-safe): the theme is under
Settings (`id:PlacesSettingsButton`) → Appearance → `id:ThemeDarkButton` or `id:ThemeLightButton`; go back
(`id:SettingsBackButton`), open Chats (`id:PlacesChatsButton`; two match, use the enabled one) and the chat "Fix
keyboard gap on resume". Untick the bezel (Avalonia MCP `click_control #ShowBezel`), size the window with
`stage_window.py <hwnd> park 820 1401` and capture. At 100% display scaling the phone's screen is then at
`--crop=204,289,616,1181` (412×892); `images.py` scales it up to the page's 492 px, and a capture at higher display
scaling is sharper. Capture only the chat: the preview's Settings page shows its sample profile. Close the preview by
PID.
