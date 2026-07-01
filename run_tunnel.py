import subprocess, threading, sys, os, re, time, signal

log_file = os.path.join(os.environ['TEMP'], 'tunnel_url.txt')

def capture():
    with open(log_file, 'w') as f:
        proc = subprocess.Popen(
            ['ssh', '-o', 'StrictHostKeyChecking=accept-new',
             '-o', 'ServerAliveInterval=30',
             '-R', '80:localhost:8080', 'localhost.run'],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1)
        for line in proc.stdout:
            f.write(line)
            f.flush()
            print(line, end='', flush=True)
            m = re.search(r'https://[\w.-]+\.localhost\.run', line)
            if m:
                with open(log_file.replace('tunnel_url', 'tunnel_url_final'), 'w') as ff:
                    ff.write(m.group(0))
    proc.wait()

threading.Thread(target=capture, daemon=True).start()
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
