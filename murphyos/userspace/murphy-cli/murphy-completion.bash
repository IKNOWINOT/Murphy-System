# murphy-completion.bash — Bash completion for the murphy CLI
# © 2020 Inoni Limited Liability Company | Creator: Corey Post | License: BSL 1.1
# Source:  eval "$(murphy --bash-completion)" or
# Install: cp murphy-completion.bash /etc/bash_completion.d/murphy

_murphy_complete() {
    local cur prev words cword
    _init_completion || return

    local commands="status forge swarm gate engine log confidence config pqc llm backup telemetry cgroup module version"
    local swarm_cmds="list spawn kill"
    local gate_cmds="list approve deny"
    local engine_cmds="list start stop"
    local log_cmds="tail search"
    local config_cmds="get set"
    local pqc_cmds="status rotate verify"
    local llm_cmds="status usage health"
    local backup_cmds="create list verify restore"
    local telemetry_cmds="status dump"
    local cgroup_cmds="list usage"
    local module_cmds="list start stop status"
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
        llm)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${llm_cmds}" -- "${cur}") )
            fi
            ;;
        backup)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${backup_cmds}" -- "${cur}") )
            fi
            ;;
        telemetry)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${telemetry_cmds}" -- "${cur}") )
            fi
            ;;
        cgroup)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${cgroup_cmds}" -- "${cur}") )
            fi
            ;;
        module)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "${module_cmds}" -- "${cur}") )
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
