#!/usr/bin/env python3
"""hetzner_ddns.py
Minimal DynDNS updater for Hetzner DNS API (standard library only).
Supports token from:
 - /usr/local/etc/hetzner_ddns.conf
 - ENV API_TOKEN
 - 1Password CLI (op) -> Item "Hetzner DDNS" Field API_TOKEN
"""
import os, sys, time, json, urllib.request, urllib.parse, logging
from pathlib import Path
# Configuration
CONFIG_PATHS = [Path("/usr/local/etc/hetzner_ddns.conf"), Path("/etc/hetzner_ddns.conf")]
DEFAULT_INTERVAL = 60
DEFAULT_TTL = 60
HETZNER_API = "https://dns.hetzner.com/api/v1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def load_env_from_file(path):
    env = {}
    try:
        text = path.read_text()
    except Exception:
        return env
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            v = v.strip().strip('"').strip("'")
            env[k.strip()] = v
    return env

def get_config():
    cfg = {}
    for p in CONFIG_PATHS:
        if p.exists():
            logging.info(f"Loading config from {p}")
            cfg.update(load_env_from_file(p))
            break
    # env overrides
    cfg.update(os.environ)
    cfg.setdefault("INTERVAL", str(DEFAULT_INTERVAL))
    cfg.setdefault("TTL", str(DEFAULT_TTL))
    cfg.setdefault("IPV4", "true")
    cfg.setdefault("IPV6", "true")
    return cfg

def fetch_token_from_op():
    """Try to fetch token via 1Password CLI (op).
    Expects an item titled 'Hetzner DDNS' with a field 'API_TOKEN'.
    Returns token str or None.
    """
    try:
        from subprocess import check_output, CalledProcessError
        try:
            out = check_output(["op", "item", "get", "Hetzner DDNS", "--fields", "API_TOKEN", "--raw"], stderr=open('/dev/null','w'))
            token = out.decode().strip()
            if token:
                logging.info("Token fetched from 1Password (op).")
                return token
        except CalledProcessError:
            pass
        try:
            out = check_output(["op", "item", "get", "Hetzner DDNS", "--format", "json"])
            j = json.loads(out.decode())
            fields = j.get("fields", [])
            for f in fields:
                if f.get("label", "").upper() == "API_TOKEN" or f.get("id", "").upper() == "API_TOKEN":
                    return f.get("value")
        except CalledProcessError:
            pass
    except Exception as e:
        logging.debug(f"1Password (op) check failed: {e}")
    return None

def hetzner_request(path, method="GET", data=None, api_token=None, query=None):
    url = HETZNER_API + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    headers = {"User-Agent": "hetzner-ddns-script/1.0"}
    if api_token:
        headers["Auth-API-Token"] = api_token
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_text = resp.read().decode()
            if resp_text:
                return json.loads(resp_text)
            return {}
    except urllib.error.HTTPError as e:
        logging.error(f"HTTPError {e.code} for {method} {url}: {e.read().decode()}")
    except Exception as e:
        logging.error(f"Error for {method} {url}: {e}")
    return None

def find_zone(api_token, zone_name):
    resp = hetzner_request("/zones", api_token=api_token, query={"name": zone_name})
    if not resp or "zones" not in resp:
        logging.error("Could not fetch zones.")
        return None
    for z in resp["zones"]:
        if z.get("name") == zone_name:
            return z
    return None

def list_records(api_token, zone_id):
    resp = hetzner_request("/records", api_token=api_token, query={"zone_id": zone_id, "per_page": 500})
    if not resp or "records" not in resp:
        logging.error("Could not fetch records.")
        return []
    return resp["records"]

def update_record(api_token, record_id, payload):
    return hetzner_request(f"/records/{record_id}", method="PUT", data=payload, api_token=api_token)

def create_record(api_token, payload):
    return hetzner_request("/records", method="POST", data=payload, api_token=api_token)

def fetch_public_ip_v4():
    try:
        with urllib.request.urlopen("https://ipv4.icanhazip.com", timeout=10) as r:
            return r.read().decode().strip()
    except Exception as e:
        logging.debug("IPv4 lookup failed: " + str(e))
        return None

def fetch_public_ip_v6():
    try:
        with urllib.request.urlopen("https://ipv6.icanhazip.com", timeout=10) as r:
            return r.read().decode().strip()
    except Exception as e:
        logging.debug("IPv6 lookup failed: " + str(e))
        return None

def run():
    cfg = get_config()
    token = os.environ.get("API_TOKEN") or cfg.get("API_TOKEN")
    if not token:
        token = fetch_token_from_op()
    if not token:
        logging.error("API_TOKEN is missing (in /usr/local/etc/hetzner_ddns.conf, ENV or 1Password). Aborting.")
        return

    zone_name = cfg.get("ZONE")
    if not zone_name:
        logging.error("ZONE is missing in config. Aborting.")
        return

    records = cfg.get("RECORDS", "@").split()
    interval = int(cfg.get("INTERVAL", DEFAULT_INTERVAL))
    ttl = int(cfg.get("TTL", DEFAULT_TTL))
    ipv4_enabled = cfg.get("IPV4", "true").lower() in ("1", "true", "yes")
    ipv6_enabled = cfg.get("IPV6", "true").lower() in ("1", "true", "yes")

    zone = find_zone(token, zone_name)
    if not zone:
        logging.error(f"Zone {zone_name} not found in Hetzner account.")
        return
    zone_id = zone["id"]
    logging.info(f"Zone found: {zone_name} (id={zone_id})")

    while True:
        try:
            public_v4 = fetch_public_ip_v4() if ipv4_enabled else None
            public_v6 = fetch_public_ip_v6() if ipv6_enabled else None
            logging.info(f"Public IPs: v4={public_v4} v6={public_v6}")

            existing_records = list_records(token, zone_id)

            for rec_name in records:
                api_name = "" if rec_name == "@" else rec_name
                # A
                if ipv4_enabled and public_v4:
                    found = next((r for r in existing_records if r.get("name")==api_name and r.get("type")=="A"), None)
                    if found:
                        if found.get("value") != public_v4:
                            logging.info(f"A record {rec_name}.{zone_name} change {found.get('value')} -> {public_v4}")
                            payload = {"zone_id": zone_id, "type": "A", "name": api_name, "value": public_v4, "ttl": ttl}
                            update_record(token, found["id"], payload)
                        else:
                            logging.debug(f"A record {rec_name} is up to date.")
                    else:
                        logging.info(f"A record {rec_name} not found -> create {public_v4}")
                        payload = {"zone_id": zone_id, "type": "A", "name": api_name, "value": public_v4, "ttl": ttl}
                        create_record(token, payload)
                # AAAA
                if ipv6_enabled and public_v6:
                    found6 = next((r for r in existing_records if r.get("name")==api_name and r.get("type")=="AAAA"), None)
                    if found6:
                        if found6.get("value") != public_v6:
                            logging.info(f"AAAA record {rec_name}.{zone_name} change {found6.get('value')} -> {public_v6}")
                            payload = {"zone_id": zone_id, "type": "AAAA", "name": api_name, "value": public_v6, "ttl": ttl}
                            update_record(token, found6["id"], payload)
                        else:
                            logging.debug(f"AAAA record {rec_name} is up to date.")
                    else:
                        logging.info(f"AAAA record {rec_name} not found -> create {public_v6}")
                        payload = {"zone_id": zone_id, "type": "AAAA", "name": api_name, "value": public_v6, "ttl": ttl}
                        create_record(token, payload)

            time.sleep(interval)
        except KeyboardInterrupt:
            logging.info("Interrupted by user.")
            break
        except Exception as e:
            logging.error("Exception in main loop: " + str(e))
            time.sleep(interval)

if __name__ == "__main__":
    run()
