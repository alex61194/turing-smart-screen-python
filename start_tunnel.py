import subprocess, re, sys, os, time

cf_path = os.path.join(os.environ['TEMP'], 'cloudflared.exe')
outfile = os.path.join(os.environ['TEMP'], 'cf_url.txt')

proc = subprocess.Popen(
    [cf_path, 'tunnel', '--url', 'http://localhost:8080'],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, bufsize=1
)

with open(outfile, 'w') as f:
    for line in proc.stdout:
        f.write(line)
        f.flush()
        print(line, end='', flush=True)
        m = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
        if m:
            url_file = outfile.replace('cf_url', 'cf_final')
            with open(url_file, 'w') as uf:
                uf.write(m.group(0))
            print(f"\nURL: {m.group(0)}", flush=True)

proc.wait()
