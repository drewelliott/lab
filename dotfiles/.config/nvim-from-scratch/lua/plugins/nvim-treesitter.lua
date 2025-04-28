return {
    "nvim-treesitter/nvim-treesitter",
    build = ":TSUpdate",
    config = function () 
        local configs = require("nvim-treesitter.configs")

        configs.setup({
            ensure_installed = { 
                "c", 
                "lua", 
                "vim", 
                "vimdoc", 
                "query", 
                "javascript", 
                "html", 
                "bash", 
                "python",
                "cmake",
                "comment",
                "csv",
                "dockerfile",
                "editorconfig",
                "git_config",
                "gitignore",
                "go",
                "gotmpl",
                "groovy",
                "helm",
                "jinja",
                "jinja_inline",
                "json",
                "json5",
                "make",
                "markdown",
                "nix",
                "perl",
                "proto",
                "r",
                "regex",
                "robot",
                "rust",
                "sql",
                "ssh_config",
                "terraform",
                "tmux",
                "toml",
                "yaml",
                "yang",
            },

            sync_install = false,
            highlight = { enable = true },
            indent = { enable = true },

            incremental_selection = {
                enable = true,
                keymaps = {
                    init_selection = "<Enter>", -- set to 'false' to disable one of the mappings
                    node_incremental = "<Enter>",
                    scope_incremental = false,
                    node_decremental = "<Backspace>",
                },
            },

            indent = {
                enable = true
            },

        })
    end
 }
