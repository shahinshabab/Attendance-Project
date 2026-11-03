set -eu
: "${ATTENDANCE_DOMAIN:?Attendance domain is required}"
: "${ATTENDANCE_RELEASE:?Attendance release path is required}"
if ! command -v caddy >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends curl ca-certificates gpg debian-keyring debian-archive-keyring apt-transport-https
    key_directory=$(mktemp -d)
    trap 'rm -rf "$key_directory"' EXIT
    curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key -o "$key_directory/caddy.asc"
    gpg --batch --dearmor --output "$key_directory/caddy.gpg" "$key_directory/caddy.asc"
    curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt -o "$key_directory/caddy.list"
    sudo install -m 644 "$key_directory/caddy.gpg" /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    sudo install -m 644 "$key_directory/caddy.list" /etc/apt/sources.list.d/caddy-stable.list
    sudo apt-get update -qq
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends caddy
fi
sudo install -d -m 755 /etc/caddy/attendance.d
site_file=$(mktemp)
sed "s/ATTENDANCE_DOMAIN/$ATTENDANCE_DOMAIN/g" "$ATTENDANCE_RELEASE/deploy/Caddyfile" > "$site_file"
sudo install -m 644 "$site_file" "/etc/caddy/attendance.d/$ATTENDANCE_DOMAIN.caddy"
rm -f "$site_file"
if ! sudo grep -Fxq 'import /etc/caddy/attendance.d/*.caddy' /etc/caddy/Caddyfile; then
    sudo cp -n /etc/caddy/Caddyfile /etc/caddy/Caddyfile.before-attendance
    printf '\nimport /etc/caddy/attendance.d/*.caddy\n' | sudo tee -a /etc/caddy/Caddyfile >/dev/null
fi
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl enable --now caddy.service
sudo systemctl reload caddy.service
systemctl is-active caddy.service
