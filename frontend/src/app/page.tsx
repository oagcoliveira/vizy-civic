import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen bg-white">
      {/* Hero */}
      <section className="bg-brand-900 text-white py-24 px-6 text-center">
        <h1 className="text-5xl font-bold mb-4">Vizy</h1>
        <p className="text-xl text-brand-100 max-w-xl mx-auto mb-8">
          Acompanhe votações, discursos e financiamentos dos seus deputados e
          senadores — de forma simples e transparente.
        </p>
        <div className="flex gap-4 justify-center">
          <Link
            href="/cadastro"
            className="bg-brand-500 hover:bg-brand-700 text-white font-semibold px-6 py-3 rounded-lg"
          >
            Criar conta
          </Link>
          <Link
            href="/deputados"
            className="border border-white hover:bg-white hover:text-brand-900 text-white font-semibold px-6 py-3 rounded-lg transition"
          >
            Ver deputados
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-6 max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8">
        {[
          {
            title: "Votações nominais",
            body: "Saiba como cada parlamentar votou em todas as votações nominais da Câmara e do Senado.",
          },
          {
            title: "Resumos por IA",
            body: "Projetos de lei e discursos resumidos em linguagem simples, sem juridiquês.",
          },
          {
            title: "Financiamento eleitoral",
            body: "Veja quem financiou a campanha do seu representante nas eleições de 2018 e 2022.",
          },
        ].map((f) => (
          <div key={f.title} className="p-6 border rounded-xl">
            <h3 className="text-lg font-semibold mb-2">{f.title}</h3>
            <p className="text-gray-600 text-sm">{f.body}</p>
          </div>
        ))}
      </section>
    </main>
  );
}
