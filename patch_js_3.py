with open("miro-clone/static/app.js", "r") as f:
    code = f.read()

# Fix handleRemoteUpdate to use activeUsers before it's used if activeUsers isn't in scope
# wait activeUsers is at the top of the file now

with open("miro-clone/static/app.js", "w") as f:
    f.write(code)
