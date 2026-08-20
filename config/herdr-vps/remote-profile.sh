# Herdr VPS shell paths. Safe to source repeatedly from Bash or Zsh.
case ":${PATH:-}:" in
  *":$HOME/.hermes/bin:"*) ;;
  *) PATH="$HOME/.hermes/bin${PATH:+:$PATH}" ;;
esac
case ":${PATH:-}:" in
  *":$HOME/.grok/bin:"*) ;;
  *) PATH="$HOME/.grok/bin${PATH:+:$PATH}" ;;
esac
case ":${PATH:-}:" in
  *":$HOME/.local/bin:"*) ;;
  *) PATH="$HOME/.local/bin${PATH:+:$PATH}" ;;
esac
export PATH
