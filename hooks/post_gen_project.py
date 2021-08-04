import os
target = os.getcwd()

# replaces all occurrences of $((INSTALL)) with the full path of the directory
# installed to
for root, dirs, fns in os.walk(target):
    for fn in fns:
        fn = os.path.join(root, fn)
        with open(fn) as fh:
            content = fh.read()
        content = content.replace("$((INSTALL))", target)
        with open(fn, "w") as fh:
            fh.write(content)
