"""Self-contained cPanel updater V69: system loan-plan settings, add-plan modal, and quick-call address SMS.
Requires the V68 application source. Place beside manage.py and run with the app Python.
It verifies hashes, backs up source and SQLite, migrates, runs checks, and restarts Passenger.
"""
import base64
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zlib

PAYLOAD = """
eNq1W1uT28aV/ivwuGKSCcnB/ULO0OskSpWrcqvYtS+SitUAGkNkQIAGwBlNuFMVuyLZD3rfh33Li2TlorXlbNbZqjxk/wTHfssv2XO6AbABApyRNlFpZgig
+3Sfc75zRXNzRDwvWcd5dryi6TLMsjCJs/Hq6miyOUoi/2hyZBJKfcWQ/UBzNJ/aOnU9RzUczVQNzVR04huO6zou1VxTV2TieqYNA3WCdxXdPhoexfQSCMmB
GlBPNjwf/puuaznUlb3AcXxN9QLZUHQgZNq6rXiOjXMDQwPqvqE6MM4wgBD1wzw7mty/rxrWEH+O3pa2z759evNEunm8/f3NZ9sv4Rp+3TzZ/vf2C+nm45sn
3z6Vbj69efzNE7j3DAZuv7j5DO893r68+c3ff/305lOkIG2fw8SvvnkJYz7Fh19tX2y/+PYpn/L1zeOb38Ddb5/ChG8+B0ovtzDlGYx7hoP/cPObB/HbjCZM
wWkvpO1vceZL2MX2CyD9fPtn6ZvP4cMX8BFGSH/73fYFbhN2D1RwwiuY9wpuPv7b/yAX8HH8IP75vV/85P0PPnj/Zz+d/+Teh+/d73nrLE+WNM3GXrR250sS
kzPaeyidSv0HsQT/ep10e0M+4rvznwHZ9z68lSiMHzyIH8RHDx9eD4+qQccLGHMR0ss6UhRFUVXX9BWVOJoeWL7qBI5HZbjnyoZLTDUwHIW6pqUBigLDdjVK
dVMLAtcgMvUqpGjEDZRAlRUnoJZsEtnUZNnTAx1U7piuQW3Dt2Rf8wPF0f2AurpHAt8IDMUzqKL4IlJ0zRnqujw8kop/PyBRNE7cX1IvB25TSnLaRw6H9y3F
GuIPG5rR2J8D+lKaZSDb8zD2pdNTqQc77EkELtwkifop/WhNs3z885998OH4jOb9njivNxhwgYdBnR7Oj5NcWpBsvrO7ito6o+lQ6nnJcrmOQ4/kzCgZhSi8
oL3BhJPFfykJMyr9vCLyQxqH1O/3AHmvEMKofYnB7hXgFUD8Gfz5ZPs1msBfGb4ff/M5g6jEYP2MwffluFcoHsSiO0PLECTogQRBJN2CtBV7aCvO68zQ5CH+
VDOaKjgVL4blJHWIP9WkhpgFKTFyy2wOt9dRDlsRx83hSb8+lm26gPtw/1GhKOrP3avTmtY6x87z5JzGp0GvWHSEMhlt8Pd4dX7da8wc1C+Rs2r74+R8sr/O
EoiC0QJO1p4Hn0s0AZBERf8WXdL2FfN34LBuPgMf+Ql3WDuQgPfjCBAXoFFGD61L0zRJd6sK+y2GDEpHktPlKgLlZ8dV9AnjnKYB8eg8o3kexmfZeJEvo51z
CQLLsVzFMW1CVNXTdAM+BxbMMCxPp9QKdMcHf2Fatm3iY91QVVN1Xc3UFEcjlXNRTcOluuP64JcU4hjgeMzAtjXTcBxZtlVVdj0auKqjeVZguTTwfMf0Ndf1
PVVzac25mEMT0Lf5Duqnw4dKYSwhMgQ7z6TvXJ8QyYsI4PrBUeaOLmkExk4fHEmLlAZwD0iu00igOWE0V2lylpJl1gMKMDjLryIKo3P6KB/51EtS5iomcRID
rdlJtiKxuEzoJTHc//uTVyfH+Gx24ocXs5OFOmuGjD8DFP6wC47MaTw+OYaRJ6sZDHqOMNn+hQfBTxA1MOUpupEX2+c3nwph9dn2a7xX+BUed/ECsHjzGRL+
L/RFbWt+glETPRai96ubJ3h/+7JwVWKkxYDMfNbJ8Wp2csx4arKerCiwLpE0JKNF6PtgiiC3dI1y+vuvvy7lcUxmIHrwDaBQEPEeXl2S0QYwPcUzPd0nmqxr
LoQpTdUcS4bg5gNifENWA9vwNHhsG7ILsRFuKxQwqGqqQQzH2EU9R9UsV/Ud1SW6C7+IbttO4LqEqi7QMD1bg/xJhezKlH1Tg9BIAzMwDEM3DU0xRWA6mjGE
YXV/ij6tkEgQ0UdSCHyBH6JoetIZWY00afUIf12N1LEhpWCZPvVH0VmB8NLRgVUn0QVAeklybzEmq9U8JkvKwmMFWB4kO6YAtvmUt3BKE9nu2ciN1nRkyjIq
A9wO3FwkMH0Cjy4XsO9jRRb0JOUpibMQsQ869klORl66HK1D4HQdjpnSiCY+SlKfpvBUk0H/PJo4mj10dGN4hBeKLKtD+KXVJVhYeum1xtzG52jfWbulJykM
X4NaxpgvdY/JriCcLMdgoEF4tk5p98jXcjOcNWDEQG4ADwUHd1uOuamGRyp5n+x77MIr/TMwVgEGMda+8v8PNWj2YQwS9SkuwD5kx3Mup2qdOXpQZv+4InMy
s85su8unNAPom4SPfSr7mjocO/7pWvoHm/Vsn2XGds3RX44MiQVDzkqnw98FwFYVdkQ/NrZF8qDgVq12h5FdJTX/aB1653NMA+fLxCdRI7oQSGkgI6GBZREM
MZbiWoanWgGRoVaGulmjpk8IMR3HNAJIZ1zddaAaUjyiy1Bn7apvVYcwBENk04KQpDqqHigqDWzdsiC62DANopdlKoQGlMiBqUAJLluq5Wiaojq6GF1sSO/t
umfETEIKfZDxR94Ik+tRmeemyaUAN66KClHqowgKKXTGxZ8RBbGQyB+Bu5IAFuWlIR+bsgTAbEXCSURcGh3A9C9B4GFwNXJpfklhfY5xb51mSTpaJSFHyyGM
AVTyNInPqkXcKPHOOdqyJf8LUL8a2TLGFDGZLlJuABCjAJSWWA/VCS3zkcKpPMoEagajhg0MzHtuPpW2v4NkCjD6goH11bZWxmHOBHnZc+nmY0i7cPG//a5l
J9hfeI70eB+kaHXgpC9Y0QhpFmuCsHYHpF6fsdyK7XrWaQb71pgt0jA+H8ngw6IwpqN2V6NWYOjEgsqxwFzEzjFVsg+SOB+5YC/8TjnLkuVOlbLNhvFqnUv5
1QpzaG9BvXM3eQRYRReG2xdKRLjbBm64fUHAp8ETRQD55UiXFvBTMFaywxSqAS+1bZq4zSoIdJX8rF3QHgv8MCNuRH3B4xzgugUOHbrs9nfM2mbdkewNmDhZ
VdIDS1DrlkCWLoiP67MCbntPo+QJixGxA1Kzg5YeCJgEGM6z7Zc3j8veG1YTnYGblxlFemXIQ6VskPiJt14CurEbdC+i+PH7V+/7/V6LX+wNxozpH4cQS/Pk
7Cyi/R73kL2hFGY/Wg+mfNkLkrKWxXtVQ+qu6/RKEsBEXyAxEOmNGfoBqadSQCAwTw+FLDGwd1Xrng4ByQ6goHFUiFdQzgQetTXP9l1ZcQNTVakPEUymrqk5
NPA1m9hUsW2POqYX6G4VtnQbKirFcaDoNwLDhzpfCVTHg0CoOSa1PVPVFY1YNgkCE6p831d82zId3ZQtz3BMq16tF0HrpCoRb8/eFsqdi2MFi+PaU16sbl98
8zkbhxUrTtl+VdWsEsJPYs3pl6wdAyOKGneHdNZ+xoFY7L7EBvbNp8wCYNaL7R+xTm4rgrne3yCFn7F6/UtY6ivk9zmGnW45kdIMoGKq6qWTBSXoyUujjhIS
jyLA+SgP84h1J8rew83HICoWeOqiLdsNmw14+HQJWxyHMWSDJJrj9Zwx8W8BmcfrpXR9XUwuAiQLXBjGtv9xuyC/fQqxU1QEKgF4/bhQxC1yZrnPPqMogRHx
mBPc68bshjE2sAC5I5slSEqAuus8T+IyjPErIRaxhcAuRtUTVgRjP2QEJjYqDBnozL53cuzOkNuPwQ1CzMf3F4VMf8/aLbAmp1Iyfsy1XABA04aavrOw+hZY
cjtyiXfup8mKRwoMB6UjQV55CxHDATi/ImsXPXCxd2HbnCwEWtYH80FoyVmZ9bNHVdLP77HIBbHSvSr3hcRKSJYu/iSjTG0tHNQyigLkFZR5jrBHtk2i3GkI
gq1aa18B0P4kOBqOQXx1xF5ClfgDXN/8Ffu4+Lpr+5/bP6JzQUNlb5ww1n3JgP6cJXHMGVUdNR7gYFM80RPiXaHXDkzx9kmUZFTUgSBZGAzGhrSfAN//++8C
Xiqk1CqGNogk/pXErksdByGN/IybSA0uoQ8GAQCBC4kNwuSiNuIizELIjeacBOYZe6vyiRyQ7PO4KmEh300uqT8vY98c6tFz8JHlcvsjz9YExuTJ6w/F/c7d
QxN+mbjMP+92PboMfcplxWiItXMrQz+89+N7H96riPg0ojmtWdiMl1LMG7G5vLJiYq7o8d/YBAhTSBpAqu7su+g8BFJlllgSapBY0Gg1x+SO9VFYZVEtuXt2
fV2WHQLlQuHMV6DC+aTKdfCIwZ/i/DKJwzm4LQT4/h0Bl0GS5GjUd3KsXq3p2DSNGQsdf2Kl28c7Y6hTztbuMsyblDNywXyHYNmdvrjYceW+jgv/VWYAQq6q
GcOyLVww2li2SATEwPWG232x/cu3T3nKA84Mi8ubx1VoL/f+JslJTaZE5J9x6Azxde+4zs6KnNENVEqQzV5NztLQn0LtOVHs1aPpkjxCQ8oXE0U3ZHYjPQvj
iSyRdZ5cNwihH6sIYUU7JVF4Fo9YXTvhde20bDd4UJnCnQlEao+WzYfdyiuIy0B0oqpwwYvEibJ6JGVJBK7tbd+lGg2KB2DhfrjO+EQMo2esupxgZU1YbemH
sFRf0SBLPhu+HQTB8G1KAz0IBm08SJg9bFjpnIW/ohMFOWeXlzQ8W+QTW5anXhIl6eRt1TA16rZSWSibQlwGbFye7ggypkSCzo6gHCiWSloJrobjRq4orcRt
gnxKKqZu6XbrtmZkOG6Fs0Q2pdCRYUnRWyXvub5BlabklbrkUcTlVjRNVwxj2thnU5ysgTFiYJjEyWVKVs3NY9Bqgam5enQtiAU0R6MNdk4DCA0Tnii9KYCQ
jeumzP8RCDcEhOOikipXwoYoD/a/FDcLWFUDa28n0kLdVAYpS3opVi5lsxtjgDBZ00R6YkJ+K4PIglMXO3NMFX4shI/AUSFex3Ea8qVQmu6Qovg69e3pYcMr
Vt2l7dV2hVZa164tdGFhDOwycproaVANira3ac6HsGdu8eWeEegHoO20bFhyRaPFLbF9F3tSivHuOjof5UkSuSS9k0YUtc6cKYsgk+8Isjr87YAEXmWIEYTO
EWQcd9qOVUej0u1CCwdxwAOUC0usLVn4rzS5LB7x25siUOHCpSzxM0RN2NWo3V/jdOoX8K35ziYMO7fHFPU6pmNVcXSUsm0KsZTT2YgYNQU1MsNS7u6Xnddx
yweMje1qwl9IQWXan5SN1cGmWLCg6mieEfi32nidbtWl5S8dcIVRkdlPExB4mF9NxrpRmzTySXxG08byAfWIR8q1XEfxFK9t2l1YCTxiEKMpPiVQS/KOo7jK
XoxFd1gLU20DpHGtivNI6m+6DdOHVc07kplA5glgX4RRk2KpzPqircFOHDLL1ktA61Uj9MKvUdkBRYmtl3HGgCwBdiFt7KuIp+HYDtJBeUvX8JYyNvAeju10
ZWbdldmq6MrU0pUVcCneUU1ZIGLnftgpnwO8TCaAcfc8xJNBOQmjbAR3z+nOz3bMv4+toYclleH+gHGYVU6lElxNxhZ41DYxt89MHo2yBfEhkQlj0Lw00jCT
lOpebH+HDVxkOShJCjdtJrjzonUFwydIWmqaEQJlQ/R7tHgGfUCaUJzHkMNc7Sd0WqF67s3ljnkSf18oBlJtl/3W8pv9qVg1CzOdjrQZJl7ApHRTJnTAWzAB
YaZ5JQvUh7WXM1hNt6tRe+cCLaqqHp3WN9DueKtWHs3T0MvuYoMpXVGS97VhYXTyUAFzGzDZ2lXS1iBc11dNF7X0qCWna7Iqpgx7q9xd8rV5brMYq8Ww6xa0
3y1jkvfkwSbPmDRKxrF4czpy2dfRIbdCtHMMRRe05hd8L/CoVeHXNA1N75wfxi0UIEYYgXNQnA0/sJfn7DgqnGgK+rqFK949fA1g6m3AVMQkR0xT82TVqNpI
QOuAcwO/8qi8nca6a9WW2BmCMuEqYqG5w5BuGYbp3C0PEsgDJgsCvqeaqlkbwfJRll3cZ52h8gX6w8FQHMZ9Ze0WtvZISkmZzMryd8RAqIuB0OlOBturW7kl
G6yn6CIXM26trWJEtRg7GTo60Vy7jqQaqbJzQSKa5huBiFn3MI0dt5TjQv7lUkXVvIbmxGVZD3jD0MhBOFGOR2V9xbrCMz+8GArX0rpR3OCvESb7E/xVpu8i
CSkKN+2ZR/m4gcc7lKlGI+V37q5kp7ODUXS0xYqwhWiRQd+OHKtqSIChQyCvrBfbEPxoAjJXstVZW+1Q12xIbVYJP+EGMTf0zq+mvwLP59NHEwWy8iJLRnu4
q6uvZZB3Nhp9n3X4R8EJ7ZIzWcLoiNmtVPTvFDIt3+cBFqMcD/JF67QP46qWIwEPfsi21f1ou9dnO9iMUDubEY03jpWgg/AR1Fws15zIO3mb8vSuyaHahAqX
hy23y0PbyaO+p/HuLWdLGsnGHgo6kIrWyxEebXjVwX0rPOgr4GChJHHMi8sBa3YvSkldLKbtTcRSFWqbN61hAi1BsgRQVKkK2/6Mv/b757QT1YOdHhXSUbll
L4cbivZhOJU0Vgf7KG0zGn28LohxtbF+iNgbuc1V8bxIaL5r9V2wt6q7jjFDiJB91Hnkr1PqOmsqiMUMGvtln3SnGr1h1Y3shutlz33zdze6MtTV4dG/LKkf
kv7uxYypA8HBpu1VjAgmqJdo7i14QPPDlL8Fm/C42P6eYLPnxfd74eISjDQvj1pX2cnBqDePa81nIfE5iPy2Nmn9/cVuldYW3e2pqsp8xqGeyIE2CExtjzzs
xUpHfdfMVTr2B7Rbix5xutqeqHcSbNNORxbV9u6vkO7suxvU/USZdoGnGXp2yV/Nt4v5r+CXzYtFiz1Wq16XxqIP8esq/f7gdAbuKM5ydoDotDoZ+NGaplcf
sPw7Sfu9++wd9f77poe9wTQM+m/h5wEY0DqNp5wcBpjT99KUXI2DNFn22ZGKGtX3oqgkXGmJPQKigyGk1qf7c8oJu5Y3DB6y7vSto8s2Ns4otHHnDQoGAtLb
nYIqKbMtlxenKFXkf8wjeZ+VO6cz9qc8Ljko5JRdxd6poIY8yUl0WpLqD8YRjc/yxZRtfYyg+QG39lM28t2YXkrvx3k0/ukaT7r+CGvSvN8LyOj9X/QG44Bf
s7GD7/WEY4LiwTR+3K036ZWPmycE4SMfMi0kh4TvEW/R57HpdMb/jstm8elbfElEB2hpsMHvqhasn771FpMO5+yddzjLp6fCzSkOx+Qqx5O+MZgiZ3cmF8NP
hMHXXNbFhurCxlMVWd7EGfooUNm7LUdohTZjb1jX2OAat/XuGCzy3gVoAOfRGPTb8xbYNe8NmR4P7KbgX5DFYIoA6A+uB9Pued0L4uTBYNoN/SZKW3cfQfVQ
bF4A3mGBFo1hgBgucYoH5YCXavZ9+eG7LYPfHWdemkQRIDb515Be9jcuXZCLENKhXrYEX7XoDVkhDZcYKHvXKJmDpsm+h5YumYk+7A26gNnJNsW7wDm6sYJW
vwQz0MczlcXt78MKgwEbP16l7O8PaUDWUY76Kw2aHx3s1sjeCUT0R0yGTAHslgjMlC4h92LALI53D6aVm8bUbMwK63GZoJ2Wp8Cvh0z+HWRBHq9Ds3d9G8gE
vg7jDEffptPmYag3USwjAmopWL8LALhuAXhnNAeHxGYOGB1moZWI9mmd0ysoauIWavAESPXuZR5Z0d4777y1pwpM3wjUlDV9CMsCKTannHvr1DvBo3I8/UHL
kf3d1xiXiRtGdB6DlZ6xb2XMozA+bx7a96GCVUxfdkw/cDTFMa3AtkmgBZYqE4XKpmF6vmoFrmkpgReYlmnppqmbtuYT2SZmdWjf8wxDczzdtzxV9j1FlzXf
DQzV9ywS+PitAMshnqu7rqwZthYEji3LrqkSVaOWqda+a6YM1fIruUP4f/SGX7Z/re9G7n2DuJTkmAtyJ0cuRqRRkmj7lrFj4LG1u32LoOUL6Nf/B4Jj+7Y=
"""
PAYLOAD_SHA256 = 'fe3e0575b264536490179316272e923306f97a3957ac68a248aa2012612eb711'
ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    if not (ROOT / 'manage.py').is_file():
        raise RuntimeError('Place this script beside manage.py.')
    os.chdir(ROOT)
    lock_path = ROOT / '.workflow_v69_update.lock'
    lock = open(lock_path, 'a')
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another V69 update is already running.')
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / 'workflow_v69_update.log'
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, 'a', encoding='utf-8') as log:
        def say(message):
            print(message, flush=True)
            log.write(message + '\n'); log.flush()
        env = os.environ.copy()
        env['DJANGO_SETTINGS_MODULE'] = 'crm.settings'
        def run(*args):
            result = subprocess.run([sys.executable, *args], cwd=ROOT, env=env,
                                    stdout=log, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError('Command failed: ' + ' '.join(args[:3]))
        try:
            say('Starting system loan-plan settings and quick-call address SMS V69 update.')
            packed = base64.b64decode(''.join(PAYLOAD.split()), validate=True)
            if sha(packed) != PAYLOAD_SHA256:
                raise RuntimeError('Script payload is incomplete or changed. Copy the entire script again.')
            specs = json.loads(zlib.decompress(packed))
            updates = {}
            for name, spec in specs.items():
                path = ROOT / name
                if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
                    raise RuntimeError('Unsafe file path: ' + name)
                raw = path.read_bytes() if path.exists() else None
                old = raw.replace(b'\r\n', b'\n') if raw is not None else None
                digest = sha(old) if old is not None else None
                if digest == spec['new']:
                    continue
                if digest != spec['old']:
                    raise RuntimeError('File differs from supported V68 source; no files changed: ' + name)
                lines = old.decode('utf-8').splitlines(keepends=True) if old is not None else []
                for start, end, replacement in reversed(spec['edits']):
                    lines[start:end] = replacement.splitlines(keepends=True)
                new = ''.join(lines).encode('utf-8')
                if sha(new) != spec['new']:
                    raise RuntimeError('Patch verification failed: ' + name)
                if name.endswith('.py'):
                    compile(new, name, 'exec')
                updates[name] = new
            say('Verified V68 source. Files to update: ' + str(len(updates)))
            info = subprocess.run([sys.executable, '-c',
                'import json; from django.conf import settings; d=settings.DATABASES["default"]; print(json.dumps([d["ENGINE"],str(d["NAME"])]))'],
                cwd=ROOT, env=env, capture_output=True, text=True)
            if info.returncode:
                log.write(info.stderr)
                raise RuntimeError('Cannot load Django settings; no files changed.')
            engine, database_name = json.loads(info.stdout)
            if engine != 'django.db.backends.sqlite3':
                raise RuntimeError('V69 installer currently requires SQLite; no files changed.')
            db = Path(database_name)
            if not db.is_absolute(): db = ROOT / db
            if not db.is_file():
                raise RuntimeError('SQLite database not found; no files changed.')
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = ROOT / 'backups' / ('workflow-v69-' + stamp)
            backup.mkdir(parents=True, mode=0o700); backup.chmod(0o700)
            for name in updates:
                source = ROOT / name
                if source.exists():
                    saved = backup / 'files' / name
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, saved)
            with sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True) as source:
                with sqlite3.connect(backup / 'database.sqlite3') as target:
                    source.backup(target)
                    if target.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                        raise RuntimeError('Database backup verification failed.')
            (backup / 'database.sqlite3').chmod(0o600)
            say('Backup created: ' + str(backup))
            for name, content in updates.items():
                path = ROOT / name
                path.parent.mkdir(parents=True, exist_ok=True)
                mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
                fd, temporary = tempfile.mkstemp(prefix='.workflow-v69-', dir=path.parent)
                try:
                    with os.fdopen(fd, 'wb') as file:
                        file.write(content); file.flush(); os.fsync(file.fileno())
                    os.chmod(temporary, mode)
                    os.replace(temporary, path)
                finally:
                    if os.path.exists(temporary): os.unlink(temporary)
            say('Application files updated. Applying migrations and synchronizing tasks...')
            run('manage.py', 'migrate', '--noinput')
            run('manage.py', 'sync_workflow_tasks')
            run('manage.py', 'check')
            run('manage.py', 'migrate', '--check')
            smoke = """import django
django.setup()
import inspect
from accounts.permissions import PERMISSIONS
from customers.forms import HubCallForm
from customers.sms import SmsDeliveryResult, send_address_sms
from communications.models import MessageTemplate, TestRun
from django.template.loader import get_template
assert 'communications.send_live' in PERMISSIONS
assert MessageTemplate.objects.filter(channel='sms', name='ارسال آدرس').exists()
assert 'requested_by' in inspect.signature(send_address_sms).parameters
assert 'request_token' in inspect.signature(send_address_sms).parameters
assert bool(SmsDeliveryResult(True, 'ok'))
assert not bool(SmsDeliveryResult(False, 'error'))
assert 'send_address' in HubCallForm().fields
get_template('customers/_call_modal.html')
get_template('customers/_quick_call_modal.html')
get_template('customers/club_program_settings.html')
from pathlib import Path
quick = Path('templates/customers/_quick_call_modal.html').read_text(encoding='utf-8')
plans = Path('templates/customers/club_program_settings.html').read_text(encoding='utf-8')
base = Path('templates/base.html').read_text(encoding='utf-8')
assert 'qc-send-address-row' in quick and quick.index('qc-send-address-row') < quick.index('qc-notes')
assert 'data-open-new-program' in plans and 'data-new-program-modal' in plans
assert plans.index('loan-list-count') < plans.index('data-open-new-program')
assert base.index('تنظیمات سیستم') < base.rindex('تنظیمات طرح‌های وام')
print('LOAN SETTINGS AND QUICK ADDRESS SMS V69 SMOKE CHECK PASSED')
"""
            run('-c', smoke)
            restart = ROOT / 'tmp'; restart.mkdir(exist_ok=True)
            (restart / 'restart.txt').touch()
            say('SUCCESS: V69 installed, migrations/checks passed, Passenger restart requested.')
            say('Loan plans are under system settings; add-plan uses a modal; quick new-call can send the address SMS.')
            say('Log: ' + str(log_path))
        except Exception as error:
            say('FAILED: ' + str(error))
            say('See logs/workflow_v69_update.log. Backup is preserved; database is not auto-restored.')
            raise SystemExit(1)

if __name__ == '__main__':
    main()
