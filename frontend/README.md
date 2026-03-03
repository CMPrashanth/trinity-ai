# Trinity Agent - Frontend

Modern, responsive React frontend for the Trinity Agent autonomous pentesting platform.

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ or Bun
- Backend API running (see `../backend/README.md`)

### Development

**Using Bun (Recommended)**:
```bash
bun install
bun dev
```

**Using npm**:
```bash
npm install
npm run dev
```

The app will be available at http://localhost:5173

## 📁 Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── dashboard/        # Dashboard widgets
│   │   ├── layout/           # Layout components (Navbar, Footer)
│   │   └── ui/               # shadcn/ui components
│   ├── pages/                # Route pages
│   │   ├── Index.tsx         # Dashboard home
│   │   ├── Scan.tsx          # Scan configuration
│   │   ├── Graph.tsx         # Attack graph visualization
│   │   ├── Vulnerabilities.tsx
│   │   ├── Logs.tsx          # Activity logs
│   │   ├── Settings.tsx      # User settings
│   │   └── Auth.tsx          # Login/Register
│   ├── hooks/                # Custom React hooks
│   ├── lib/                  # Utilities
│   └── App.tsx               # Main app component
├── public/                   # Static assets
└── package.json
```

The only requirement is having Node.js & npm installed - [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating)

Follow these steps:

```sh
# Step 1: Clone the repository using the project's Git URL.
git clone <YOUR_GIT_URL>

# Step 2: Navigate to the project directory.
cd <YOUR_PROJECT_NAME>

# Step 3: Install the necessary dependencies.
npm i

# Step 4: Start the development server with auto-reloading and an instant preview.
npm run dev
```

**Edit a file directly in GitHub**

- Navigate to the desired file(s).
- Click the "Edit" button (pencil icon) at the top right of the file view.
- Make your changes and commit the changes.

**Use GitHub Codespaces**

- Navigate to the main page of your repository.
- Click on the "Code" button (green button) near the top right.
- Select the "Codespaces" tab.
- Click on "New codespace" to launch a new Codespace environment.
- Edit files directly within the Codespace and commit and push your changes once you're done.

## What technologies are used for this project?

This project is built with:

- Vite
- TypeScript
- React
- shadcn-ui
- Tailwind CSS

## How can I deploy this project?

Simply open [Lovable](https://lovable.dev/projects/REPLACE_WITH_PROJECT_ID) and click on Share -> Publish.

## Can I connect a custom domain to my Lovable project?

Yes, you can!

To connect a domain, navigate to Project > Settings > Domains and click Connect Domain.

Read more here: [Setting up a custom domain](https://docs.lovable.dev/features/custom-domain#custom-domain)
