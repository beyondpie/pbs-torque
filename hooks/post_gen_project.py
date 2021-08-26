import os
target = os.getcwd()

# replace $((USER)) in config file with the user name
user = os.getlogin()
with open("config.yaml") as config_fh:
    config_content = config_fh.read()
config_content = config_content.replace("$((USER))", user)
with open("config.yaml", "w") as config_fh:
    config_fh.write(config_content)

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
