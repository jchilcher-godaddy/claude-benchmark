# Blog Post Corrections for techloom.it

## Summary of Changes

The techloom.it blog post needs these corrections:

---

## 1. GitHub Repository URL (2 locations)

### Current (WRONG):
```
github.com/jchilcher/claude-benchmark
```

### Change to:
```
github.com/jchilcher-godaddy/claude-benchmark
```

**Locations:**
- Paragraph 3: "If you want the data, everything is open source at claude-benchmark"
- Final "Try It Yourself" section: "All data and methodology: github.com/jchilcher/claude-benchmark"

---

## 2. Add Task Structure Clarification

The commenter couldn't find Go/JS/C# tasks. Add this note after the first mention of "212,000+ benchmarks across Python, Go, JavaScript, and C#":

### Add after paragraph 1:
```html
<div class="result-highlight">
<strong>Finding the cross-language tasks:</strong> Tasks for each language follow a naming convention: <code>bug-fix-01</code> (Python), <code>bug-fix-01-go</code> (Go), <code>bug-fix-01-js</code> (JavaScript), <code>bug-fix-01-cs</code> (C#). All 48 tasks (12 per language) are in the <code>tasks/builtin/</code> directory. Cross-language experiments use <code>experiments/cross-language.toml</code> and <code>experiments/cot-cross-language.toml</code>.
</div>
```

---

## 3. Remove or Update Broken Internal Links

These internal links reference experiment pages that were deleted during the scrub. Options:

**Option A - Remove links entirely (recommended):**
Change linked text to plain text. For example:
- Change: `<a href="/blog/chain-of-thought-experiment/">chain-of-thought</a>`
- To: `chain-of-thought`

**Option B - Link to experiment TOML files in GitHub:**
- Change: `<a href="/blog/chain-of-thought-experiment/">chain-of-thought</a>`
- To: `<a href="https://github.com/jchilcher-godaddy/claude-benchmark/blob/main/experiments/chain-of-thought.toml">chain-of-thought</a>`

**Broken links to update:**
1. `/blog/chain-of-thought-experiment/`
2. `/blog/politeness-sweep-experiment/`
3. `/blog/persona-sweep-experiment/`
4. `/blog/context-pollution-experiment/`
5. `/blog/model-selection-experiment/`
6. `/blog/verification-instructions-experiment/`
7. `/blog/multi-turn-conversation-experiment/`
8. `/blog/language-kitchen-sink-experiment/`
9. `/blog/init-vs-best-practices-experiment/`
10. `/blog/emotional-stakes-experiment/`
11. `/blog/output-compression-experiment/`
12. `/blog/capstone-v2-experiment/`
13. `/blog/cross-language-revisits-experiment/`
14. `/blog/compress-claude-md/`

---

## 4. "Try It Yourself" Section - Full Replacement

### Current:
```
The benchmark tool, all 13 profiles, and the experiment configurations are open source:

If your CLAUDE.md beats empty on your tasks, you've found something genuinely useful. If it doesn't, you've just freed up context window for the conversation that actually matters.

All data and methodology: github.com/jchilcher/claude-benchmark
```

### Replace with:
```html
<p>The benchmark tool, all experiment configurations, and cross-language tasks are open source:</p>

<pre><code>git clone https://github.com/jchilcher-godaddy/claude-benchmark.git
cd claude-benchmark
pip install -e .

# Run a quick benchmark
claude-benchmark run --claudemd path/to/your/CLAUDE.md

# Run a cross-language experiment
claude-benchmark experiment experiments/cross-language.toml --direct-api -c 50 -y</code></pre>

<p><strong>Task structure:</strong> The repo includes 48 tasks across 4 languages (12 each). Python tasks are named <code>bug-fix-01</code>, <code>code-gen-01</code>, etc. Other languages append a suffix: <code>bug-fix-01-go</code>, <code>bug-fix-01-js</code>, <code>bug-fix-01-cs</code>.</p>

<p>If your CLAUDE.md beats empty on your tasks, you've found something genuinely useful. If it doesn't, you've just freed up context window for the conversation that actually matters.</p>

<p>All data and methodology: <a href="https://github.com/jchilcher-godaddy/claude-benchmark">github.com/jchilcher-godaddy/claude-benchmark</a></p>
```

---

## Quick Find/Replace Summary

| Find | Replace |
|------|---------|
| `github.com/jchilcher/claude-benchmark` | `github.com/jchilcher-godaddy/claude-benchmark` |
| `href="/blog/chain-of-thought-experiment/"` | (remove href, keep text) |
| `href="/blog/capstone-v2-experiment/"` | (remove href, keep text) |
| (other internal experiment links) | (remove href, keep text) |

---

## Verification Checklist

After updating:
- [ ] GitHub links point to `jchilcher-godaddy/claude-benchmark`
- [ ] Task naming convention is explained (Python: `bug-fix-01`, Go: `bug-fix-01-go`, etc.)
- [ ] No broken internal links to deleted experiment pages
- [ ] "Try It Yourself" section has correct repo URL and explains task structure
