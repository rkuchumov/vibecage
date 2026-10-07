#!/bin/sh

# 1. Temporarily patch DNS to download sidecar dependencies
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 1.1.1.1" >> /etc/resolv.conf

apk add --no-cache dnsmasq ipset iptables tcpdump >/dev/null 2>&1

# 2. Point container DNS back to localhost
echo "nameserver 127.0.0.1" > /etc/resolv.conf

# 3. Create kernel IP set
ipset create whitelist hash:ip

# 4. Build dnsmasq configuration
cat << 'EOF' > /etc/dnsmasq.conf
listen-address=127.0.0.1
bind-interfaces
no-resolv
log-queries=extra
log-facility=-
EOF

# Upstream nameservers are only queried for whitelisted domains
while read -r domain; do
  domain=$(echo "$domain" | tr -d '\r' | grep -v '^#' | grep -v '^$')
  if [ -n "$domain" ]; then
    echo "server=/$domain/8.8.8.8" >> /etc/dnsmasq.conf
    echo "server=/$domain/1.1.1.1" >> /etc/dnsmasq.conf
    echo "ipset=/$domain/whitelist" >> /etc/dnsmasq.conf
  fi
done < /whitelist.txt

# Start dnsmasq in background, logging directly to stdout
dnsmasq -k &

# 5. Configure iptables
iptables -F
iptables -P OUTPUT DROP

iptables -A OUTPUT -o lo -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow dnsmasq upstream DNS lookups
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

# Allow whitelisted IPs dynamically collected by ipset
iptables -A OUTPUT -m set --match-set whitelist dst -j ACCEPT

# Drop, log to NFLOG, and reject any unauthorized packet
iptables -A OUTPUT -j NFLOG --nflog-group 1
iptables -A OUTPUT -j REJECT

exec tcpdump -i nflog:1 -n -l

