
vim.opt.expandtab = true -- Convert tabs to spaces
vim.opt.shiftwidth = 4 -- Amount to indent with << and >>
vim.opt.tabstop = 4 -- How many spaces are shown per Tab
vim.opt.softtabstop = 4 -- How many spaces are applied when pressing Tab

vim.opt.smarttab = true
vim.opt.smartindent = true
vim.opt.autoindent = true -- Keep indentation from previous line
vim.opt.breakindent = true -- Enable break indent

-- Always show relative line numbers
vim.opt.number = true 
vim.opt.relativenumber = true 

-- Show line under cursor
vim.opt.cursorline = true 

-- Store undos between sessions
vim.opt.undofile = true 

-- Enable mouse mode
vim.opt.mouse = "a" 

-- This is handled by statusline plugin
vim.opt.showmode = false 

-- Case-insensitive searching uncless \C or one or more capital letters in the search term
vim.opt.ignorecase = true
vim.opt.smartcase = true

--Keep signcolumn on by default
vim.opt.signcolumn = "yes" 

-- Configure how new splits should be opened
vim.opt.splitright = true
vim.opt.splitbelow = true

-- Sets how neovim will display certain whitespace characters in the editor.
-- See `:help 'list'`
-- See `:help 'listchars'`
vim.opt.list = true
vim.opt.listchars = { tab = '» ', trail = '·', nbsp = '␣' }

-- Preview substitutions live, as you type!
vim.opt.inccommand = "split"

-- Minimal number of screen lines to keep above and below the cursor.
vim.opt.scrolloff = 5

-- Disable commandline until it is needed. This gives us a cleaner look and an extra line ;)
-- vim.opt.cmdheight = 0

-- Highlight when yanking (copying) text
--  Try it with `yap` in normal mode
--  See `:help vim.highlight.on_yank()`
vim.api.nvim_create_autocmd('TextYankPost', {
  desc = 'Highlight when yanking (copying) text',
  group = vim.api.nvim_create_augroup('kickstart-highlight-yank', { clear = true }),
  callback = function()
    vim.highlight.on_yank()
  end,
})



