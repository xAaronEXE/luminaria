# Testing Luminaria 0.2.6

Work top to bottom. Each check says what to do and what you should see. Write down
anything that does not match, with the exact message shown.

## 1. Merge the changes

1. Open https://github.com/xAaronEXE/luminaria/pull/3 and click **Merge pull request**,
   then **Confirm merge**.
2. Open https://github.com/xAaronEXE/luminaria/pull/2 and click **Close pull request**.
   Its change is already included in #3.

## 2. Build and publish 0.2.6

Open PowerShell and paste this whole block:

```powershell
cd C:\Users\desse\Desktop\Luminaria
git checkout main
git pull origin main
Get-Content .\VERSION
powershell -ExecutionPolicy Bypass -File .\build.ps1
powershell -ExecutionPolicy Bypass -File .\publish-release.ps1
```

- `Get-Content .\VERSION` prints `0.2.6`.
- The build takes several minutes and ends with no red text.
- The last line is a link ending in `/releases/tag/v0.2.6`.
- If `git pull` says local changes would be overwritten, run `git stash push -u`
  and paste the block again.

Then open
https://luminaria-identity.johnnycox4431836.workers.dev/releases/latest. It shows
`"version":"0.2.6"`.

## 3. Update from inside the app

Do this before installing anything by hand, so the updater itself gets tested.

1. Open your installed Luminaria 0.2.5.
2. Go to **Settings & updates → Updates**. It shows 0.2.6 with the release notes.
3. Click **Install 0.2.6** and confirm. The download is checked, then the installer opens.
   Windows may warn that it is unsigned. Click **More info → Run anyway**.
4. After it restarts, **Settings & updates** shows 0.2.6.
5. Your chats, memories, My files and downloaded models are all still there.

## 4. Feature checks

### Trash

- [ ] Archive a test chat, then move it to the trash. Open **Archive & trash** and
      click **Delete permanently**. Confirm. It disappears and does not come back
      after restarting the app.
- [ ] Put two chats in the trash and click **Empty trash (2)**. Both are gone.

### Attachments

- [ ] Plus button → **Attach files** → choose a PDF. Ask "summarize this". The answer
      uses the PDF's content. The original is in My files → Attachments.
- [ ] Do the same with a Word `.docx` file.
- [ ] Try a password-protected PDF. You get a clear refusal, not a crash.
- [ ] Plus button → **Attach a folder** → choose a small code folder. The model gets
      a list of its files and can read them. A copy is in My files → Imports.
- [ ] The plus menu is fully visible, not cut off at the top or bottom.

### Models

- [ ] **Model library** → click an installed model to open its details → **Run quality check**. It takes a
      few minutes and shows a score out of 12 with a per-question breakdown.
- [ ] **Run speed test** still works and is listed separately from quality.

### Skills

- [ ] Open **Skills**. Skills are grouped (Planning & writing, Code, GitHub, Browser &
      desktop, Automation, Skills). Each shows **Ready** or **Needs setup**.
- [ ] **Needs setup** filter: each skill says what it needs, for example
      "GitHub integration".
- [ ] Turn on **Computer and command tools** in **Settings → Tools & permissions**,
      reopen Skills. Coding and new-repo now show **Ready**.
- [ ] Import: choose a `.md` file under **Load from a .md file**, then **Save skill**.
      It appears under **Imported** with a **Remove** button. Remove it.
- [ ] Click **Use in this task** on a skill. The message box starts with `/skill name`.

### Integrations

Open **Tools & integrations → Integrations**.

- [ ] **GitHub:** create a token at https://github.com/settings/personal-access-tokens/new
      (only the repos you want, read-only is fine). Paste it and click **Connect**.
      Within a few seconds the badge reads **Connected · N tools**. Ask Luminaria
      "list my GitHub repositories".
- [ ] **Linear** or **Notion** (whichever you use): click **Connect with browser**.
      Your browser opens the service's approval page. Approve. The browser tab says
      "Signed in", and Luminaria shows **Connected**.
- [ ] Click **Disconnect** on one. It returns to **Not connected**. Restart Luminaria;
      it stays disconnected.
- [ ] Restart Luminaria with one still connected. It reconnects without signing in again.
- [ ] Deny or close a browser sign-in. The card shows the cancellation instead of
      pretending to be connected.
- [ ] Optional: Slack and Google need your own OAuth app. Each card explains the setup
      and has a **Copy** button for the redirect URL.

### 3D core and voice

- [ ] Start a voice conversation. The core looks different when it is listening,
      thinking, speaking, when you interrupt it, and on an error (for example, with the
      model server stopped).

### Model problems

- [ ] With a model loaded, close the model manager process (Task Manager → end
      `llama-swap.exe`), then send a message. A notice says it is restarting, and the
      reply still arrives.
- [ ] Make a fake model file: in PowerShell run
      `Set-Content C:\Users\desse\Desktop\broken.gguf "not a model"`. In
      **Models → Add a local GGUF model**, register it with ID `broken-test` and that
      path, restart Luminaria, select it and send a message. The error says the model
      file could not be loaded, instead of only a server code. Switch back to your real
      model and remove `broken-test` afterwards.

### Activity history

- [ ] In the right panel, open **Activity → All chats**. Actions from every chat appear,
      newest first. Choose **Errors, denials and interruptions** to see only problems.
      Search for a file name you used. Click a chat name to open that chat.

### Required sign-in (optional, last)

Only do this after sign-in itself works and you are online.

- [ ] Sign in with GitHub in **Settings → Accounts**, then close and reopen Luminaria.
- [ ] Turn on **Require sign-in on this PC**. Close and reopen. Luminaria opens normally.
- [ ] Click **Sign out**. The sign-in screen covers the app, and nothing else works.
      Sign in again, then close and reopen. You are back in.
- [ ] Turn it off again in Accounts. If you are ever locked out, close Luminaria, open
      `C:\Users\desse\Desktop\Luminaria\App\data\profiles.json` in Notepad,
      delete the `"require_sign_in": true` line (and the comma before it), save, and
      reopen.

### Panels

- [ ] Stop the model server and open each sidebar panel. Each shows Loading…, then
      either its content or an error with **Try again**.
- [ ] In Ivory (light) mode, text fields have clearly visible borders.

## 5. Not yet tested anywhere

These were built and tested only with simulated services, so your results here are
the first real evidence:

- Real GitHub, Linear, Notion, Slack and Google connections.
- A quality check against a real model.
- PDF, Word and folder attachments in the installed app.
- The in-app update from 0.2.5 to 0.2.6.
- Model crash recovery and load-failure explanations with a real model.
- Required sign-in with the real sign-in service.
