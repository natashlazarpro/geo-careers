# GeoCareers — GIS employers

**Where maps get made.** GeoCareers is an interactive web map of companies that hire GIS and geodata professionals. You can filter by city, sector, role type, company size, working language and tech stack. Click any marker to open a company card with a direct link to the company's careers page.

**Live site:** https://geocareers.app

## Features

- **Interactive Mapbox map**, with one marker per office, colour-coded by sector
- **Map, Employers and Cities views.** The employer directory lists each company once, and offices in several cities are merged into one row.
- **City coverage** of major cities plus regional GIS hubs
- **13 sectors**, including renewable energy, surveying & geodesy, remote sensing, hydrology, environment & conservation, and urban & transport planning
- **Multi-filter panel:** city, sector, GIS role type (core product / dedicated team / side tool), company size, working language and tech stack
- **Company cards** with a description, tech tags, a Kununu rating link and a careers page link
- **Bilingual UI:** switch between English and German
- **Secure data serving** through a Cloudflare Worker, so company data never lives in the repo

## Tech stack

| Layer    | Tool |
|----------|------|
| Map      | [Mapbox GL JS v3](https://docs.mapbox.com/mapbox-gl-js/) |
| Frontend | Vanilla HTML/CSS/JS, with no build step |
| Data API | [Cloudflare Workers](https://workers.cloudflare.com/) |
| Domain   | geocareers.app (Cloudflare) |
| Hosting  | GitHub Pages |

## Costs

Everything runs on free tiers:

- **GitHub Pages:** free
- **Cloudflare Workers:** 100,000 requests/day free
- **Mapbox:** 50,000 map loads/month free

The domain is the only paid item.

## Help GeoCareers grow

GeoCareers is free and independent, and I build it in my spare time. If you'd like to help it grow, there are two ways:

📝 **Share your feedback (2 min).** Tell me what's missing and what to build next: https://forms.gle/F9BaWSMgJ686XdXg6

☕ **Support the project.** If the map helped your job search, you can buy me a coffee. It helps cover hosting and data costs: https://buymeacoffee.com/natashlazarpro

This version exists because of you.

## License

[MIT](LICENSE) © Nataliia Lazareva
