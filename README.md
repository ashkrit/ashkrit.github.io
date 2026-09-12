# ashkrit.github.io

Personal profile site — [ashkrit.github.io](https://ashkrit.github.io)

Plain static HTML, CSS and JavaScript. No framework, no build step, no dependencies.
GitHub Pages serves `main` directly.

## Layout

```
index.html                  the whole page
assets/css/style.css        styles
assets/js/site.js           rendering, filters, theme toggle
data/profile.json           ← the only file to hand-edit
data/posts.json             generated from the blog feed
data/repos.json             generated from the GitHub API
scripts/sync.py             the generator (Python stdlib only)
.github/workflows/sync.yml  runs the generator daily
```

## Editing your details

Everything personal lives in `data/profile.json` — name, role, bio, focus areas,
links, experience and education.

Fields still containing `TODO` are **hidden from the rendered page**, so partial
data never leaks on to the site. Fill them in or delete the entry.

## How syncing works

`scripts/sync.py` rewrites `data/posts.json` and `data/repos.json` from:

- the Blogger feed at `ashkrit.blogspot.com/feeds/posts/default?alt=json`
- `api.github.com/users/ashkrit/repos`

If either source fails, the existing file is left untouched and the script exits
non-zero — a bad upstream response can never blank the site.

The workflow runs daily and commits only when the data actually changed. It can
also be run by hand from the Actions tab (**Run workflow**).

Run it locally the same way:

```sh
python3 scripts/sync.py
```

## Local preview

`fetch()` is blocked on `file://` URLs, so open the site over HTTP:

```sh
python3 -m http.server 8000
# → http://localhost:8000
```
