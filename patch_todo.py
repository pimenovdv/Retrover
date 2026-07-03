with open("miro-clone/TODO.md", "r") as f:
    todo = f.read()

todo = todo.replace("- [ ] Display other users' cursors in real-time.", "- [x] Display other users' cursors in real-time.")
todo = todo.replace("- [ ] Show who is currently selecting/editing an object to avoid conflicts.", "- [x] Show who is currently selecting/editing an object to avoid conflicts.")
todo = todo.replace("- [ ] Add a chat or comment system.", "- [x] Add a chat or comment system.")

with open("miro-clone/TODO.md", "w") as f:
    f.write(todo)
