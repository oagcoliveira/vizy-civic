type Props = { params: { id: string } };

export default function PoliticianPage({ params }: Props) {
  return (
    <main className="max-w-5xl mx-auto px-6 py-12">
      <p className="text-gray-400 text-sm mb-4">Perfil do parlamentar</p>
      <h1 className="text-3xl font-bold mb-8">Carregando...</h1>

      {/* Tabs placeholder */}
      <div className="border-b flex gap-6 mb-8 text-sm font-medium text-gray-500">
        {["Atividade recente", "Votações", "Discursos", "Projetos de Lei", "Comissões", "Doadores"].map(
          (tab) => (
            <button key={tab} className="pb-3 hover:text-brand-700">
              {tab}
            </button>
          )
        )}
      </div>

      <p className="text-gray-400">Selecione uma aba para ver o conteúdo.</p>
    </main>
  );
}
