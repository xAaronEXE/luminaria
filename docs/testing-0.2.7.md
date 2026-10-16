# Testing Luminaria 0.2.7

These checks cover the expanded model library. Everything in testing-0.2.6.md
still applies. Write down anything that does not match, with the exact message shown.

## 1. Library and storage

1. Open **Settings & updates → Models**.
   - The storage bar shows your model drive, used and free space.
   - The tabs read **All 30**, **Standard 15**, **Abliterated 15** and **Installed**
     with your installed count.
2. Click **Vision**. Only the four Gemma 3 models are listed. Click **Vision** again
   to clear it.
3. Type `coder` in the search box. Only Qwen Coder models are listed.
4. Select **Gemma 3 12B Abliterated**.
   - It has the cracked Abliterated mark and the abliteration note.
   - **Context** shows `32,768 configured` and `131,072 supported`.
   - **Source** is a link to the publisher page at a pinned revision.
   - The storage bar gains a striped section for the selected download, and the
     legend shows **Free afterward**.

## 2. A real download

Pick a small model so this does not take long: **Qwen3 4B Abliterated · Q4_K_M**
(2.3 GB) or **Gemma 3 4B · Q4_K_M** (2.3 GB).

1. Click **Download**. The progress bar and percentage move, and the list row shows
   `Downloading`.
2. Click **Pause download**, wait a few seconds, then **Resume download**. It
   continues from where it stopped rather than from zero.
3. Let it finish. The row shows `Q4_K_M installed` and the quantization shows
   `Installed · verified`.
4. Click **Use this model**, then send a short message in a new chat. It answers.
5. Click **Benchmark → Run speed test**. A speed and first-token time appear and
   stay after you reopen Models.

## 3. Vision projector (Gemma 3 only)

1. With **Gemma 3 4B** selected, click **Add · 811.8 MB** under Vision projector.
   It downloads and then shows `Downloaded and verified`.
2. Select **Gemma 3 4B Abliterated**. Its projector already shows as downloaded,
   because they share the same file.
3. Click **Use this model** on the Gemma model you downloaded, attach an image in a
   new chat and ask what it shows. It describes the image.
4. Try **Remove** on the projector while that model is active. It refuses and
   explains why.

## 4. Cancel and remove

1. Start another download, click **Pause download**, then **Cancel and delete
   partial**. The progress disappears and the storage numbers drop back.
2. Remove a model you downloaded with **Remove file**. It asks first, and the
   storage bar updates afterward.
