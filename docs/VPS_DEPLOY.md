# 🌐 Deploying Jarvis OS on a VPS

Run Jarvis OS on a remote server and access the dashboard from anywhere.

---

## Quick Start (5 minutes)

### Step 1: SSH into your VPS

```bash
ssh root@your-server-ip
```

### Step 2: Install Docker (if not already installed)

```bash
curl -fsSL https://get.docker.com | sh
```

### Step 3: Install Jarvis OS

```bash
curl -fsSL https://raw.githubusercontent.com/mitrescuvasile300/jarvis-os/main/install.sh | bash
```

### Step 4: Access the Dashboard

You have **3 options**, from simplest to most robust:

---

## Option A: SSH Tunnel (Simplest — No Config Needed)

**Best for:** Personal use, quick access, maximum security.

From **your local computer** (not the VPS), run:

```bash
ssh -L 8080:localhost:8080 root@your-server-ip
```

Then open in your browser: **http://localhost:8080**

The dashboard runs on the VPS but appears as if it's local. All traffic is encrypted through SSH.

**Make it permanent** — add to `~/.ssh/config`:
```
Host jarvis-vps
    HostName your-server-ip
    User root
    LocalForward 8080 localhost:8080
```

Then just: `ssh jarvis-vps` and open `http://localhost:8080`.

---

## Option B: Nginx + SSL with Let's Encrypt (Professional)

**Best for:** Custom domain, HTTPS, sharing with teammates.

### 1. Point your domain to the VPS

Add an A record: `jarvis.yourdomain.com → your-server-ip`

### 2. Install Nginx and Certbot

```bash
apt update && apt install -y nginx certbot python3-certbot-nginx
```

### 3. Create Nginx config

```bash
cat > /etc/nginx/sites-available/jarvis << 'EOF'
server {
    listen 80;
    server_name jarvis.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
EOF

ln -s /etc/nginx/sites-available/jarvis /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 4. Get SSL certificate (free)

```bash
certbot --nginx -d jarvis.yourdomain.com
```

### 5. (Optional) Add password protection

```bash
apt install -y apache2-utils
htpasswd -c /etc/nginx/.htpasswd jarvis
```

Add to nginx config inside `location /`:
```
auth_basic "Jarvis OS";
auth_basic_user_file /etc/nginx/.htpasswd;
```

Now access: **https://jarvis.yourdomain.com**

---

## Option C: Cloudflare Tunnel (Zero Ports, Free)

**Best for:** No open ports needed, works behind NAT, free SSL.

### 1. Install cloudflared on VPS

```bash
curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared
```

### 2. Login to Cloudflare

```bash
cloudflared tunnel login
```

### 3. Create tunnel

```bash
cloudflared tunnel create jarvis
cloudflared tunnel route dns jarvis jarvis.yourdomain.com
```

### 4. Create config

```bash
cat > ~/.cloudflared/config.yml << EOF
tunnel: jarvis
credentials-file: /root/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: jarvis.yourdomain.com
    service: http://localhost:8080
  - service: http_status:404
EOF
```

### 5. Run as service

```bash
cloudflared service install
systemctl start cloudflared
```

Now access: **https://jarvis.yourdomain.com** (no ports open, fully encrypted)

---

## Security Checklist

- [ ] Never expose port 8080 directly to the internet without auth
- [ ] Use SSH tunnel or Nginx + SSL for encrypted access
- [ ] Keep your API keys in `.env` (never commit them)
- [ ] Use a firewall: `ufw allow ssh && ufw allow 80 && ufw allow 443 && ufw enable`
- [ ] Set up automatic Docker updates

---

## VPS Providers (Recommended)

| Provider | Price | Good For |
|----------|-------|----------|
| [Hetzner](https://hetzner.cloud) | €4.50/mo | Best value, EU servers |
| [DigitalOcean](https://digitalocean.com) | $6/mo | Simple, good docs |
| [Vultr](https://vultr.com) | $6/mo | Many locations |
| [Oracle Cloud](https://cloud.oracle.com) | **Free** | ARM instances, always free tier |
| [Contabo](https://contabo.com) | €5/mo | Cheap, high specs |

**Minimum specs:** 1 vCPU, 1GB RAM, 20GB disk (2GB+ RAM if using Ollama).

---

## Docker Commands on VPS

```bash
# Check status
docker compose ps

# View logs
docker compose logs -f

# Restart
docker compose restart

# Stop
docker compose down

# Update to latest version
cd jarvis-os && git pull && docker compose up -d --build

# Backup data
tar -czf jarvis-backup.tar.gz jarvis-os/data jarvis-os/.env
```
