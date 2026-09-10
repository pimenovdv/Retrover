with open("miro-clone/static/app.js", "r") as f:
    content = f.read()

print("initApp definition found:", "function initApp()" in content)
print("initApp invocation found:", "initApp()" in content)
