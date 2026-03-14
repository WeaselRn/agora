import subprocess, json

try:
    out = subprocess.check_output("npx --yes pyright --outputjson research.py runner.py", shell=True)
except subprocess.CalledProcessError as e:
    out = e.output

try:
    data = json.loads(out)
    with open("errors.txt", "w", encoding="utf-8") as f:
        for e in data.get("generalDiagnostics", []):
            filename = e["file"].replace("\\", "/").split("/")[-1]
            f.write(f"{filename}:{e['range']['start']['line']+1} - {e['rule']}: {e['message']}\n")
except Exception as exc:
    print("Error:", exc)
