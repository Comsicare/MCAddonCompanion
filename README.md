# MCAddonCompanion

A desktop companion app for Minecraft that handles schematic syncing, instance backups, and a self-hosted mod pack registry — all through a clean dark UI.

Currently supports **Prism Launcher**. Multi-launcher support (MultiMC, Modrinth App, CurseForge, Official Launcher) is planned for v0.6.0.

---

## Features

| Module | What it does |
|---|---|
| **Schematic Sync** | Auto-syncs Create, Litematica, and Schematica schematics to a Nextcloud folder on game exit |
| **Instance Sync** | Backs up and restores full Prism instance folders via Nextcloud on launch/exit |
| **Pack Registry** | Publish, version, and distribute mod packs via a self-hosted GitLab repository |

---

## Installation

Download the latest installer from [GitHub Releases](https://github.com/Comsicare/MCAddonCompanion/releases).

- **Windows**: run `MCAddonCompanion-Setup.exe`
- **Linux**: extract `MCAddonCompanion-Linux.tar.gz` and run the `MCAddonCompanion` binary

The app checks for updates automatically on launch and shows a banner when a newer version is available.

---

## Module Guide

### Schematic Sync

Enable autosync per instance in the **Schematic Sync** tab. On game exit, any `.nbt`, `.litematic`, or `.schematic` files are copied to your configured archive folders (Nextcloud by default).

---

### Instance Sync

Keeps your Prism instance folders in sync across multiple PCs via a shared folder (Nextcloud, etc.).

**Setup:**
1. Go to **Instance Sync** → click the gear icon next to the page title
2. Enter your Prism instances path and a sync folder path
3. Click **Save** — hooks are written to `instance.cfg` automatically

**Per-instance controls:**
- Toggle **Exit Sync** / **Startup Sync** per instance from the home page gear icon or the Instance Sync page
- **Archive** — syncs the instance, creates a zip backup, then removes it from Prism
- **Archive (Move only)** — syncs and removes without creating a zip (no restore available)
- Archived instances can be restored from the Instance Sync page

---

### Pack Registry

The Pack Registry lets you publish versioned mod packs to a self-hosted GitLab repository and install them on any machine running MCAddonCompanion.

#### Setting up a GitLab repository as a Pack Registry

You need a GitLab project with the **Generic Package Registry** enabled (available on all tiers, including free self-hosted).

**Step 1 — Create the GitLab project**

1. Create a new GitLab project (e.g. `mc-packs`)
2. Set visibility to **Public** if you want anonymous downloads, or **Private** if you want to require authentication
3. No special project settings needed — the Generic Package Registry is enabled by default

**Step 2 — Create a Personal Access Token (for browsing/listing)**

1. In GitLab go to **User Settings → Access Tokens**
2. Create a token with `api` scope
3. Copy the token — it starts with `glpat-`

**Step 3 — Create a Deploy Token (for publishing)**

1. In your GitLab project go to **Settings → Repository → Deploy tokens**
2. Create a token with `write_package_registry` scope
3. Copy the token — it starts with `gldt-`

> If your project is **public**, only the deploy token is needed for publishing. The PAT is required for listing packages (the GitLab API requires authentication for package listing even on public projects).

**Step 4 — Add the repo in MCAddonCompanion**

1. Go to **Pack Registry → Repos → Add**
2. Paste your GitLab project URL (e.g. `https://gitlab.example.com/yourname/mc-packs`)
3. Paste your **Personal Access Token** in the PAT field
4. Paste your **Deploy Token** in the Deploy Token field
5. Click **Test connection** then **Save**

---

#### Publishing a pack

1. Go to **Pack Registry → Publish**
2. Select the **Repo** and the **Instance** to export from
3. **Pack Name** — select an existing pack to publish a new version, or click **+ New** to create a new pack
4. Enter a **Version** string (e.g. `1.0.0`) — free text, no format enforced
5. Fill in **Description** and **Changenotes**
6. Check the **Include** boxes for what to bundle (mods, config, resourcepacks, etc.)
7. In the **Mod Side Tags** table, set each mod as `required`, `client`, or `server`. Check **Exclude** to omit a mod entirely
   - Tags are pre-filled from the previous version automatically when updating an existing pack
8. Verify **Loader Version** is filled (shown with a red `!` if missing)
9. Click **Publish pack**

---

#### Installing a pack

1. Go to **Pack Registry → Browse**
2. Select a repo, then select a pack from the left list
3. Choose a version — changenotes and mod diff (added/removed) are shown
4. Choose **Create new instance** or **Install to existing**
5. Optionally check **Track for updates**
6. Click **Install** — conflict resolution dialog appears if needed

---

#### Managing installed packs

Go to **Pack Registry → Instances** to see all instances installed from the registry. Update, reinstall, or untrack from here. Tracked instances with **Auto Update** enabled get an update prompt on game launch via the startup hook.

---

## Update Streams

The app updates itself automatically. To change which releases you receive, open the **three-dot menu → Version & Updates** and select a stream:

| Stream | Receives |
|---|---|
| `alpha` | All pre-release builds (default) |
| `beta` | Beta + stable |
| `prerelease` | Release candidates + stable |
| `release` | Stable releases only |

---

## Diagnostics

Go to **three-dot menu → Help & Debug** to:
- View host info (version, paths, platform)
- Reset individual modules
- Save a **debug dump** — a zip containing app logs and a redacted copy of your settings, useful for bug reports

---

## Roadmap

| Version | Goal |
|---|---|
| **v0.3.0-alpha** | Logging, archive modal, full UI wiring ✅ |
| **v0.4.0-alpha** | Polish existing modules — archive pre-flight, instance sync conflict detection, small fixes |
| **v0.5.0-alpha** | Stability, efficiency, and performance — file operation optimization, code audit |
| **v0.6.0-alpha** | Multi-launcher support — Prism, MultiMC, Modrinth App, CurseForge, Official Launcher |
| **v0.7.0-alpha** | Setup wizard / welcome tour for first-time configuration |
| **v0.8.0-alpha** | Code audit, bugfixing, diagnostic upload for easier support |
| **v1.0.0-pre** | User testing and feedback |
| **v1.0.0** | Stable release |

---

## Running from source

```bash
git clone https://gitlab.comsicare.com/Comsicare/MCAddonCompanion.git
cd MCAddonCompanion
python main.py          # creates venv and installs deps on first run
```

No build step needed — the frontend is plain HTML/CSS/JS (Vue 3 ESM, no bundler).

---

## License

MIT
