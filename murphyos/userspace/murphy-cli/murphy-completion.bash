# murphy-completion.bash — Bash completion for the murphy CLI
# © 2020 Inoni Limited Liability Company | Creator: Corey Post | License: BSL 1.1
# Source:  eval "$(murphy --bash-completion)" or
# Install: cp murphy-completion.bash /etc/bash_completion.d/murphy

_murphy_complete() {
    local cur prev words cword
    _init_completion || return

    local commands="status forge swarm gate engine log confidence config pqc version"
    local swarm_cmds="list spawn kill"
    local gate_cmds="list approve deny"
    local engine_cmds="list start stop"
    local log_cmds="tail search"
    local config_cmds="get set"
    local pqc_cmds="status rotate verify"
    local global_opts="--json -q --quiet --api-url --help"

    # Determine position
    case "${cword}" in
        1)
            COMPREPLY=( $(compgen -W "${commands} ${global_opts}" -- "${cur}") )
            return
            ;;
    esac

    # Subcommand completions
    case "${words[1]}" in
        swarm)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${swarm_cmds}" -- "${cur}") )
            fi
            ;;
        gate)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${gate_cmds}" -- "${cur}") )
            fi
            ;;
        engine)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${engine_cmds}" -- "${cur}") )
            fi
            ;;
        log)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${log_cmds}" -- "${cur}") )
            fi
            ;;
        config)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${config_cmds}" -- "${cur}") )
            fi
            ;;
        pqc)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${pqc_cmds}" -- "${cur}") )
            fi
            ;;
        status|confidence|version)
            COMPREPLY=( $(compgen -W "${global_opts}" -- "${cur}") )
            ;;
        *)
            COMPREPLY=()
            ;;
    esac
}

complete -F _murphy_complete murphy
