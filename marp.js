#!/bin/env bun
import fs from 'fs'
import { log } from 'console'
import Marpit from '@marp-team/marpit'
import markdownItContainer from 'markdown-it-container'

function basename(path) {
    return path.split('/').pop()
}

const file = process.argv[2]
let markdown = undefined
if (file) {
    markdown = fs.readFileSync(file, 'utf8')
} else {
    markdown = fs.createReadStream(0, 'utf8')
    log(markdown)
    log(`Usage: ${basename(process.argv[0])} ${basename(process.argv[1])} < input.md`)
    process.exit(1)
}

const marpit = new Marpit().use(markdownItContainer, 'columns')
const theme = `
/* @theme custom-container */
.columns { column-count: 2; }
`
marpit.themeSet.default = marpit.themeSet.add(theme)
const { html, css } = marpit.render(markdown)

// 4. Use output in your HTML
const htmlFile = `
<!DOCTYPE html>
<html><body>
  <style>${css}</style>
  ${html}
</body></html>
`
fs.writeFileSync(`${file}.html`, htmlFile.trim())