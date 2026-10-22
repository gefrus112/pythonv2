# Python v2 for VS Code

Syntax highlighting, indentation rules and snippets for the Python v2
language (`.pyv2` files).

## Install (no packaging needed)

Copy this folder into your VS Code extensions directory and reload:

```sh
# macOS / Linux
cp -r editors/vscode ~/.vscode/extensions/pyv2-0.1.0

# Windows (PowerShell)
Copy-Item -Recurse editors/vscode "$env:USERPROFILE\.vscode\extensions\pyv2-0.1.0"
```

Then restart VS Code (or run **Developer: Reload Window**).

## Install (as a VSIX)

```sh
cd editors/vscode
npx @vscode/vsce package
code --install-extension pyv2-0.1.0.vsix
```

## What you get

- Colorized `.pyv2` files (keywords, f-strings, numbers, comments, operators)
- Smart indentation (`fn`/`if`/`while`/`for` indent, `end`/`elif`/`else` dedent)
- Snippets: `fn`, `if`, `ifelse`, `while`, `for`, `forr`, `fstr`, `map`,
  `main`, `appdata`, and `dialog`
- Run the current file with **Ctrl+Shift+B**, validate application metadata,
  or create a Windows build kit from the included `.vscode/tasks.json` tasks

## Not using VS Code?

The full setup guides for dev containers, Codespaces, desktop terminals and
any other editor live in the project docs:
https://github.com/gefrus112/pythonv2/blob/main/docs/LANGUAGE.md
