import shlex

def pretty_print_cmd(cmd_list, max_line_length=80):
    tokens = []
    i = 0
    while i < len(cmd_list):
        arg = cmd_list[i]
        if arg.startswith('-') and i + 1 < len(cmd_list) and not cmd_list[i + 1].startswith('-'):
            tokens.append(f"{shlex.quote(arg)} {shlex.quote(cmd_list[i + 1])}")
            i += 2
        else:
            tokens.append(shlex.quote(arg))
            i += 1

    lines = []
    current_line = []
    current_length = 0

    for token in tokens:
        added_length = len(token) + (1 if current_line else 0)
        
        if not current_line or (current_length + added_length <= max_line_length):
            current_line.append(token)
            current_length += added_length
        else:
            lines.append(" ".join(current_line))
            current_line = [token]
            current_length = len(token)
            
    if current_line:
        lines.append(" ".join(current_line))

    print(" \\\n  ".join(lines))
