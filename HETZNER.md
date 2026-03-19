# Deploying Makestack to Hetzner via Cloudflare Tunnel

This guide deploys Makestack (core + shell) on a Hetzner CX21 server with Cloudflare Tunnel
handling all ingress. No ports are exposed on the server — UFW only needs SSH.

The MCP SSE endpoint (`/mcp/sse`) is protected by a Cloudflare Access service token,
which Claude Desktop and Claude Code send as custom headers.

---

## Prerequisites

- A Hetzner Cloud account
- A domain managed by Cloudflare (free plan is sufficient)
- A Cloudflare account with Zero Trust enabled (free tier covers this)
- SSH key ready for the server

---

## 1. Provision the Hetzner Server

In the Hetzner Cloud Console (console.hetzner.cloud):

1. **New Project** → create or select a project
2. **Add Server:**
   - Location: pick closest to you
   - Image: **Ubuntu 24.04**
   - Type: **CX21** (2 vCPU, 4 GB RAM) — sufficient for core + shell + cloudflared
   - SSH Key: add your public key
   - Name: `makestack`
3. Note the server's **public IP address**

---

## 2. Install Docker CE

SSH into the server, then run:

```bash
# Install Docker CE (official method for Ubuntu 24.04)
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

---

## 3. Configure the Firewall

No HTTP/HTTPS ports needed — Cloudflare Tunnel is outbound-only.

```bash
ufw allow 22/tcp
ufw enable
# Verify: ufw status
```

---

## 4. Create the Cloudflare Tunnel

In the **Cloudflare Zero Trust dashboard** (one.dash.cloudflare.com → Zero Trust):

1. **Networks → Tunnels → Create a tunnel**
2. Name: `makestack` → **Save tunnel**
3. Connector: choose **Docker** — copy the displayed token (starts with `eyJ...`)
   - You'll paste this into `.env` as `CLOUDFLARE_TUNNEL_TOKEN`
4. **Add a public hostname:**
   - Subdomain: `makestack` (or whatever you prefer)
   - Domain: your Cloudflare-managed domain
   - Service Type: `HTTP`
   - URL: `shell:3000`
5. Under **Additional application settings → HTTP Settings:**
   - Enable **"Disable chunked encoding"** — required for the MCP SSE stream to work correctly
6. Save the hostname → **Finish setup**

Your Makestack UI will be available at `https://makestack.yourdomain.com`.

---

## 5. Protect the MCP Endpoint with Cloudflare Access

This creates a service token that Claude sends as headers to authenticate MCP requests.

In the Zero Trust dashboard:

1. **Access → Applications → Add an application → Self-hosted**
2. Configure:
   - Application name: `Makestack MCP`
   - Session duration: 24 hours (or longer — Claude reconnects on expiry)
   - Application domain: `makestack.yourdomain.com`
   - Path: `mcp/sse`
3. **Next → Add a policy:**
   - Policy name: `Claude service token`
   - Action: **Service Auth**
   - Include rule: **Service Token** → create a new service token named `claude`
   - Copy the **Client ID** and **Client Secret** that appear — these are shown once
4. Save the application

---

## 6. Deploy the Code to the Server

On the server, clone the repository:

```bash
git clone <your-makestack-shell-repo-url> /opt/makestack
cd /opt/makestack
```

If `makestack/core:latest` is not published to a registry, build it first (requires
the `makestack-core` repo to be cloned alongside):

```bash
git clone <your-makestack-core-repo-url> /opt/makestack-core
docker build -t makestack/core:latest /opt/makestack-core
```

---

## 7. Configure Environment Variables

```bash
cd /opt/makestack
cp .env.hetzner.example .env
```

Edit `.env`:

```env
MAKESTACK_API_KEY=<output of: openssl rand -hex 32>
CLOUDFLARE_TUNNEL_TOKEN=eyJ...   # from Step 4
```

---

## 8. Start the Stack

```bash
cd /opt/makestack
docker compose -f docker-compose.hetzner.yml up -d --build
```

Watch the logs to confirm everything starts:

```bash
docker compose -f docker-compose.hetzner.yml logs -f
```

Expected sequence:
1. `core` starts and passes healthcheck
2. `shell` starts, runs migrations, connects to core, passes healthcheck
3. `cloudflared` connects to the Cloudflare network

Verify: open `https://makestack.yourdomain.com` in your browser — you should see the
Makestack UI.

---

## 9. Install the Kitchen Module via the UI

In the Makestack UI:

1. Go to **Settings → Package Manager → Registries**
2. Add registry: paste the `makestack-addons` repo URL
3. Go to **Package Manager → Browse**
4. Install **inventory-stock** first (kitchen depends on it)
5. Install **kitchen**
6. The shell will restart automatically to load the new modules

---

## 10. Configure Claude

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "makestack": {
      "type": "sse",
      "url": "https://makestack.yourdomain.com/mcp/sse",
      "headers": {
        "CF-Access-Client-Id": "<client-id from Step 5>",
        "CF-Access-Client-Secret": "<client-secret from Step 5>"
      }
    }
  }
}
```

Restart Claude Desktop.

### Claude Code

Create or edit `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "makestack": {
      "type": "sse",
      "url": "https://makestack.yourdomain.com/mcp/sse",
      "headers": {
        "CF-Access-Client-Id": "<client-id from Step 5>",
        "CF-Access-Client-Secret": "<client-secret from Step 5>"
      }
    }
  }
}
```

---

## 11. Verify End-to-End

In Claude, ask: *"List my Makestack modules"* or *"What tools do you have from Makestack?"*

You should see the shell tools plus the kitchen module tools (`kitchen__list_recipes`,
`kitchen__get_stock`, etc.).

---

## Maintenance

### View logs
```bash
docker compose -f docker-compose.hetzner.yml logs -f shell
```

### Update the shell
```bash
cd /opt/makestack
git pull
docker compose -f docker-compose.hetzner.yml up -d --build shell
```

### Backup UserDB
The UserDB is in the `makestack-userdb` Docker volume. The shell also creates daily
backups inside the volume at `~/.makestack/backups/`. To export manually:

```bash
docker compose -f docker-compose.hetzner.yml exec shell \
  python -m cli.main export --output /tmp/backup.json
docker cp $(docker compose -f docker-compose.hetzner.yml ps -q shell):/tmp/backup.json ./backup.json
```

### Stop everything
```bash
docker compose -f docker-compose.hetzner.yml down
# Add -v to also delete volumes (destructive — deletes all data)
```

---

## Troubleshooting

**SSE stream drops or MCP times out**
- Check the "Disable chunked encoding" setting is enabled on the public hostname in the
  Cloudflare dashboard (Step 4, step 5).
- Cloudflare free plan has a 100-second timeout on HTTP connections. MCP SSE connections
  are long-lived — upgrade to a paid plan or use Cloudflare's "No response buffering"
  setting if you hit this limit.

**`cloudflared` fails to connect**
- Verify `CLOUDFLARE_TUNNEL_TOKEN` in `.env` is the full token string.
- Check `docker compose logs cloudflared` for the specific error.

**Shell can't reach core**
- Both services must be on the `makestack` network — verify with
  `docker network inspect makestack-hetzner_makestack`.
- Check `docker compose logs core` for startup errors.

**Modules don't appear after install**
- The shell restarts automatically after module installation. Wait ~30 seconds, then
  refresh the Claude MCP connection.
