type Props = { params: { id: string } };

export default function BillPage({ params }: Props) {
  return (
    <main className="max-w-4xl mx-auto px-6 py-12">
      <p className="text-gray-400 text-sm mb-2">Projeto de Lei</p>
      <h1 className="text-3xl font-bold mb-4">Carregando...</h1>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-2">O que é?</h2>
        <p className="text-gray-600">Resumo gerado por IA aparecerá aqui.</p>
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-2">Tramitação</h2>
        <p className="text-gray-600">Linha do tempo legislativa aparecerá aqui.</p>
      </section>
    </main>
  );
}
