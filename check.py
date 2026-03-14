import subprocess, json

try:
    out = subprocess.check_output(["npx", "--yes", "pyright", "--outputjson", "research.py", "runner.py"], shell=True)
except subprocess.CalledProcessError as e:
    out = e.output

try:
    data = json.loads(out)
    for e in data.get("generalDiagnostics", []):
        print(f"{e['file']}:{e['range']['start']['line']+1} - {e['message']}")
except Exception as exc:
    print("Error parsing json:", exc)
