# MCAddonCompanion

A desktop companion app for [Prism Launcher](https://prismlauncher.org/) that handles schematic syncing, instance backups, and a self-hosted mod pack registry — all through a clean dark UI built on PyWebView + Vue 3.

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
1. Go to **Instance Sync** → click **Setup Instance Sync**
2. Enter your Prism instances path (e.g. `C:\Users\...\PrismLauncher\instances`)
3. Enter a sync folder path (e.g. `C:\Users\...\Nextcloud\Minecraft`)
4. Click **Save & Enable** — hooks are written to instance.cfg automatically

**Per-instance controls:**
- Toggle **Exit Sync** / **Startup Sync** per instance or set global defaults
- **Archive** — syncs the instance, creates a zip backup, then removes it from Prism so it disappears from the launcher
- **Archived** button — restore any archived instance back into Prism; prompts to delete the backup zip after

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
3. **Pack Name** — select an existing pack from the dropdown to publish a new version, or click **+ New** to create a new pack
4. Enter a **Version** string (e.g. `1.0.0` or `2024-05-18`) — this is free text, no format enforced
5. Fill in **Description** and **Changenotes**
6. Check the **Include** boxes for what to bundle (mods, config, resourcepacks, etc.)
7. In the **Mod Side Tags** table, set each mod as `required`, `client`, or `server`. Check **Exclude** to omit a mod from the pack entirely
   - Tags are pre-filled from the previous version automatically when updating an existing pack
8. Verify **Loader Version** is filled (shown with a red `!` if missing — an empty loader version causes a red X in Prism)
9. Click **Publish pack** — progress is shown in the panel on the right

The pack is uploaded as a GitLab Generic Package. Each named pack is one package; each version is a separate package version containing a zip and a `metadata.json` sidecar.

---

#### Installing a pack

1. Go to **Pack Registry → Browse**
2. Select a repo from the top bar, then select a pack from the left list
3. Choose a version from the dropdown — changenotes and mod diff (added/removed) are shown
4. Choose **Create new instance** or **Install to existing**
5. Optionally check **Track for updates** — tracked instances get an auto-update prompt on next game launch
6. Click **Install**
   - If installing to an existing instance and file conflicts are detected, a conflict dialog appears grouped by folder. Mark files to keep (skip overwrite) per file or per group. Identical files are skipped automatically.

---

#### Managing installed packs

Go to **Pack Registry → Instances** to see all instances ever installed from the registry.

| Column | Description |
|---|---|
| Instance | Prism instance name |
| Pack | Pack name |
| Version | Installed version |
| Repo | Source repository |
| Tracked | Whether the instance tracks updates |
| Auto Update | Toggle to enable/disable the startup update prompt hook |
| Actions | Update button (when newer version available), Untrack, or Reinstall/Remove if instance is missing from Prism |

**Auto Update** — when enabled, the `--startup` hook is written to the instance's `instance.cfg`. On next game launch, if a newer version of the pack is available, a prompt appears with changenotes and a 20-second countdown to auto-skip.

---

## Update Streams

The app updates itself automatically. The update stream controls which releases you receive:

| Stream | Receives |
|---|---|
| `alpha` | All pre-release builds (default) |
| `beta` | Beta + stable |
| `prerelease` | Release candidates + stable |
| `release` | Stable releases only |

To change stream, set `"update_stream"` in `%APPDATA%\MCAddonCompanion\state.json`.

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
