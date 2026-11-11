# Connect your own Cloudflare sync Worker

You can use a Worker in your Cloudflare account to sync encrypted Luminaria data between your PCs. Each PC needs a device key to reach the Worker and the separate sync key to decrypt your data.

Cloudflare is a separate company. Workers and D1 have free plans with usage limits. R2 has included monthly usage and requires adding an R2 subscription through checkout. Cloudflare requires a payment method for add-on subscriptions. Check checkout for supported cards and wallets. The dashboard shows current usage. Luminaria limits traffic from its own sync protocol, while Cloudflare controls account-level usage and billing.

[Workers limits](https://developers.cloudflare.com/workers/platform/limits/) · [D1 limits](https://developers.cloudflare.com/d1/platform/limits/) · [R2 setup](https://developers.cloudflare.com/r2/get-started/) · [R2 pricing](https://developers.cloudflare.com/r2/pricing/) · [Payment methods](https://developers.cloudflare.com/billing/get-started/update-billing-info/)

## Guided setup on Windows

In PowerShell 7, open this directory, run `npm ci`, and sign in with `npx wrangler login`. Preview the resources with `./setup-private-sync.ps1 -AccountId YOUR_ACCOUNT_ID -WhatIf`. Run the same command without `-WhatIf` to create them. The last line prints this PC's device key. Copy it privately into Luminaria along with the Worker URL shown by Wrangler.

If setup stops after creating a resource, use the resource name in `wrangler.private-sync.local.jsonc` to resume the matching step below. The generated name also identifies the database and bucket. Keep this file local.

## Manual setup or recovery

1. Enable R2 in the Cloudflare dashboard. From this directory, install the project's pinned dependencies with `npm ci` and run `npx wrangler login` to connect the account you own.
2. Copy `wrangler.private-sync.example.jsonc` to `wrangler.private-sync.local.jsonc`. If you have multiple accounts, set `account_id` to your account in this local copy.
3. Create a database with `npx wrangler d1 create luminaria-private-sync --config wrangler.private-sync.local.jsonc`. Put its database ID into the local configuration. Create a private bucket with `npx wrangler r2 bucket create luminaria-private-sync --config wrangler.private-sync.local.jsonc`.
4. Initialize the database with `npx wrangler d1 execute luminaria-private-sync --remote --file migrations/0005_cloud_sync.sql --config wrangler.private-sync.local.jsonc`.
5. Generate a unique device key and its hash using Python. Keep the first line private and enter it only in Luminaria on that PC. The second line goes into the Worker secret.

   ```sh
   python -c "import hashlib,json,secrets; key=secrets.token_hex(32); print(key); print(json.dumps([hashlib.sha256(key.encode()).hexdigest()]))"
   ```

6. Deploy with `npx wrangler deploy --config wrangler.private-sync.local.jsonc`. Set the Worker secret with `npx wrangler secret put SYNC_DEVICE_KEY_HASHES --config wrangler.private-sync.local.jsonc` and paste the JSON array of device-key hashes when prompted. The Worker refuses requests until it has a valid key list.
7. In Luminaria, open **Settings → Cloud sync → Use your own Cloudflare Worker**. Enter the deployed HTTPS `workers.dev` address and the device key. If adding a PC, also enter the encryption key from **Show sync key** on a connected PC. On the first PC, save the encryption key somewhere private before syncing.

Generate a different device key for each PC. To add or revoke access, replace the Worker secret with the full JSON list of allowed hashes. Revoking a device key blocks access to the Worker. If the encryption key itself is exposed, use a fresh sync key and fresh storage for future sync.
