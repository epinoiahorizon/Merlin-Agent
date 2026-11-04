# Piagam Identitas & Originalitas — Merlin Agent by Epinoia Horizon

Dokumen kanonik. Semua permukaan produk WAJIB merujuk ke sini.
Versi: 1.2 · Dibuat: 2026-10-21 · Diperbarui: 2026-11-03 · Pemilik: Epinoia Horizon (June Arthov)

## 1. Satu Nama, Satu Organisasi

- Produk: Merlin Agent
- Organisasi: Epinoia Horizon
- Repo kanonik: github.com/epinoiahorizon/Merlin-Agent
- Dilarang memakai nama lain untuk entitas yang sama ("Arthov Labs",
  "Hermes Agent", dll) di permukaan publik mana pun.

### 1a. Kebijakan Atribusi (baca sebelum menyapu nama)

- `NOTICE` dan `LICENSE` adalah **rekam legal MIT** — JANGAN dihapus atau
  dikosongkan. Mereka bukan "branding"; menyapunya = pelanggaran lisensi.
- Yang disapu dari permukaan publik: penyebutan nama lain sebagai identitas
  produk (hero README, tagline situs, meta description, banner, persona).
- Posisi atribusi di README: **bukan di hero** — cukup satu bagian
  `License & Provenance` di bawah, faktual, nada setara (bukan nada
  "kami cuma ganti nama / kami di belakang upstream").
- Merlin diposisikan sebagai produk independen buatan Epinoia Horizon yang
  dibangun di atas inti open-source berlisensi MIT. Arah jangka panjang:
  lihat `INDEPENDENCE-ROADMAP.md`.

## 2. Watermark Wajib (signature block)

Setiap artefak publik — banner CLI, README, docs, situs, balasan bot —
memuat minimal satu dari:

  Merlin Agent by Epinoia Horizon
  github.com/epinoiahorizon/Merlin-Agent

Logo ASCII kanonik (tampil di banner CLI/TUI/desktop):

  ███╗   ███╗███████╗██████╗ ██╗     ██╗███╗   ██╗
  ████╗ ████║██╔════╝██╔══██╗██║     ██║████╗  ██║
  ██╔████╔██║█████╗  ██████╔╝██║     ██║██╔██╗ ██║
  ██║╚██╔╝██║██╔══╝  ██╔══██╗██║     ██║██║╚██╗██║
  ██║ ╚═╝ ██║███████╗██║  ██║███████╗██║██║ ╚████║
  ╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚═╝╚═╝  ╚═══╝

## 3. Suara (voice)

- Langsung, berbasis bukti, tanpa filler.
- Setiap klaim teknis disertai hasil pengukuran nyata.
- Ketika ditanya identitas: "Merlin Agent, dibangun oleh Epinoia Horizon".
  Tidak pernah mengadopsi identitas lain.

## 4. Checklist Permukaan (semua wajib konsisten)

- [x] SOUL.md Windows + WSL — sudah diseragamkan 2026-10-21
- [x] Banner CLI (merlin --version / splash) — sudah Merlin penuh, diverifikasi 2026-11-03
- [ ] Nama aplikasi Desktop (window title, about page) — perlu verifikasi build Electron
- [ ] Nama bot Telegram di BotFather (ganti dari "Hermes") — aksi manual di luar repo
- [x] README GitHub + badges — prosedensi pindah ke bagian `License & Provenance`, 2026-11-03
  - [ ] OG image (aset masih perlu dibuat)
- [x] Docs header (docs.withmerlin.online/docs) — blok identitas Merlin-first, 2026-11-03
- [x] llms.txt — sudah live, identity block Merlin-first, 2026-11-03
- [ ] Persona gateway (semua platform) — perlu audit bio/about tiap adapter
- [x] Vendor `@merlin/ui` dist — teks poster "nama lama" dipatch stopgap di dist;
      sumber paket harus diperbarui + republish (lihat roadmap Fase 2)

## 5. Jejak Digital (biar LLM luar bisa "kenal")

1. Docs + llms.txt di domain kanonik — HIDUP (verifikasi 2026-10-21, HTTP 200).
2. Subdomain mati yang harus dihidupkan: grimoire, merlin-assets, docs.
3. Submit ke AI answer engine + SEO teknis (skill product-landing-seo).
4. Konsistensi nama di semua komunitas/listing.

## 6. Aturan Turunan

- Satu perubahan identitas = perbarui piagam ini DULU, lalu permukaannya.
- Piagam ini bagian dari repo, bukan catatan pribadi.
