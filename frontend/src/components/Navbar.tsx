import Link from "next/link";

export function Navbar() {
  return (
    <header className="border-b bg-white sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link href="/" className="text-xl font-bold text-primary">
            Vizy
          </Link>
          <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-muted-foreground">
            <Link href="/deputados" className="hover:text-foreground transition-colors">Deputados</Link>
            <Link href="/senadores" className="hover:text-foreground transition-colors">Senadores</Link>
            <Link href="/votacoes" className="hover:text-foreground transition-colors">Votações</Link>
            <Link href="/doacoes" className="hover:text-foreground transition-colors">Doações</Link>
            <Link href="/busca" className="hover:text-foreground transition-colors">Busca</Link>
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/login" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
            Entrar
          </Link>
          <Link href="/cadastro" className="text-sm font-medium bg-primary text-primary-foreground px-4 py-1.5 rounded-md hover:bg-primary/90 transition-colors">
            Criar conta
          </Link>
        </div>
      </div>
    </header>
  );
}
