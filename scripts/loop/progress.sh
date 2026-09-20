#!/usr/bin/env bash
# 步骤进度清单，样式对齐 gh run watch：✓ 完成 / * 进行中 / - 跳过 / ✗ 失败 / · 待执行。
# 由 dev-loop.sh 引入。终端下原地重绘整张清单，重定向到文件或管道时逐行输出。

PROG_TITLES=(); PROG_STATES=(); PROG_SUFFIX=()
PROG_CURRENT=-1; PROG_DRAWN=0; PROG_DIRTY=0; PROG_START=0
PROG_TTY=0; [ -t 1 ] && PROG_TTY=1

# 初始化清单：prog_init "步骤一" "步骤二" ...
prog_init() {
  PROG_TITLES=("$@"); PROG_STATES=(); PROG_SUFFIX=()
  local i=0
  while [ "${i}" -lt "${#PROG_TITLES[@]}" ]; do
    PROG_STATES[${i}]=pending; PROG_SUFFIX[${i}]=""; i=$((i + 1))
  done
  PROG_CURRENT=-1; PROG_DRAWN=0; PROG_DIRTY=0
  prog_render
}

# 外部命令（git push、gh run watch、ssh 等）要往屏幕上打东西之前调用，
# 之后的重绘会另起一张清单，而不是把别人的输出覆盖掉
prog_dirty() { PROG_DIRTY=1; }

prog_symbol() {
  local esc=1; [ "${PROG_TTY}" = 1 ] || esc=0
  case "$1" in
    done) [ "${esc}" = 1 ] && printf '\033[32m✓\033[0m' || printf '✓' ;;
    run)  [ "${esc}" = 1 ] && printf '\033[33m*\033[0m' || printf '*' ;;
    skip) [ "${esc}" = 1 ] && printf '\033[90m-\033[0m' || printf '-' ;;
    fail) [ "${esc}" = 1 ] && printf '\033[31m✗\033[0m' || printf '✗' ;;
    *)    [ "${esc}" = 1 ] && printf '\033[90m·\033[0m' || printf '·' ;;
  esac
}

prog_render() {
  [ "${#PROG_TITLES[@]}" -gt 0 ] || return 0
  if [ "${PROG_TTY}" != 1 ]; then return 0; fi
  if [ "${PROG_DRAWN}" = 1 ] && [ "${PROG_DIRTY}" = 0 ]; then
    printf '\033[%dA' "${#PROG_TITLES[@]}"
  else
    printf '\n'
  fi
  local i=0 title suffix
  while [ "${i}" -lt "${#PROG_TITLES[@]}" ]; do
    title="${PROG_TITLES[${i}]}"; suffix="${PROG_SUFFIX[${i}]}"
    printf '\033[2K  '
    prog_symbol "${PROG_STATES[${i}]}"
    if [ "${PROG_STATES[${i}]}" = pending ]; then
      printf ' \033[90m%s\033[0m%s\n' "${title}" "${suffix}"
    else
      printf ' %s%s\n' "${title}" "${suffix}"
    fi
    i=$((i + 1))
  done
  PROG_DRAWN=1; PROG_DIRTY=0
}

# 开始下一个待执行的步骤。各函数只管调用自己那一步，顺序由 prog_init 的清单决定，
# 这样 check / deploy 无论单独执行还是被 ship 串起来都不用关心自己排第几
prog_next() {
  local idx=0
  while [ "${idx}" -lt "${#PROG_TITLES[@]}" ]; do
    [ "${PROG_STATES[${idx}]}" = pending ] && break
    idx=$((idx + 1))
  done
  [ "${idx}" -lt "${#PROG_TITLES[@]}" ] || return 0
  PROG_CURRENT="${idx}"; PROG_STATES[${idx}]=run; PROG_START=$(date +%s)
  if [ "${PROG_TTY}" = 1 ]; then
    prog_render
  else
    printf '\n==> [%d/%d] %s\n' "$((idx + 1))" "${#PROG_TITLES[@]}" "${PROG_TITLES[${idx}]}"
  fi
}

# 结束当前步骤：prog_end done|skip|fail ["附加说明"]
prog_end() {
  local state="${1:-done}" note="${2:-}" idx="${PROG_CURRENT}" secs suffix=""
  [ "${idx}" -ge 0 ] || return 0
  if [ "${state}" = done ] || [ "${state}" = fail ]; then
    secs=$(( $(date +%s) - PROG_START ))
    [ "${secs}" -gt 0 ] && suffix=" (${secs}s)"
  fi
  [ -n "${note}" ] && suffix="${suffix} ${note}"
  PROG_STATES[${idx}]="${state}"; PROG_SUFFIX[${idx}]="${suffix}"
  PROG_CURRENT=-1
  if [ "${PROG_TTY}" = 1 ]; then
    prog_render
  else
    printf '    '; prog_symbol "${state}"; printf ' %s%s\n' "${PROG_TITLES[${idx}]}" "${suffix}"
  fi
}

# 把仍在进行中的步骤标记为失败，用于 die 和 ERR 陷阱
prog_fail_current() {
  [ "${PROG_CURRENT}" -ge 0 ] || return 0
  prog_end fail
}
