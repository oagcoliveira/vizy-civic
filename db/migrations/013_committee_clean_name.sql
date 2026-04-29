-- Add a cleaned, human-readable committee label while preserving the API-provided name.
-- Application code should display COALESCE(NULLIF(clean_name, ''), name).

ALTER TABLE core.committees
    ADD COLUMN IF NOT EXISTS clean_name VARCHAR(160);

COMMENT ON COLUMN core.committees.clean_name IS
    'Concise display label for committees. Falls back to core.committees.name when NULL or blank.';

CREATE OR REPLACE FUNCTION core.clean_committee_name(raw_name TEXT, raw_acronym TEXT)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    label TEXT;
    ac TEXT;
BEGIN
    ac := upper(nullif(trim(coalesce(raw_acronym, '')), ''));

    -- Keep the most common Câmara committees short and consistent.
    label := CASE ac
        WHEN 'CAPADR' THEN 'Agricultura'
        WHEN 'CCJC' THEN 'Constituição e Justiça'
        WHEN 'CCTI' THEN 'Ciência, Tecnologia e Inovação'
        WHEN 'CCOM' THEN 'Comunicação'
        WHEN 'CDC' THEN 'Defesa do Consumidor'
        WHEN 'CDE' THEN 'Desenvolvimento Econômico'
        WHEN 'CDU' THEN 'Desenvolvimento Urbano'
        WHEN 'CE' THEN 'Educação'
        WHEN 'CESPO' THEN 'Esporte'
        WHEN 'CFT' THEN 'Finanças e Tributação'
        WHEN 'CFFC' THEN 'Fiscalização e Controle'
        WHEN 'CMADS' THEN 'Meio Ambiente'
        WHEN 'CME' THEN 'Minas e Energia'
        WHEN 'CREDN' THEN 'Relações Exteriores e Defesa'
        WHEN 'CSPCCO' THEN 'Segurança Pública'
        WHEN 'CSSF' THEN 'Saúde'
        WHEN 'CTASP' THEN 'Trabalho e Serviço Público'
        WHEN 'CVT' THEN 'Viação e Transportes'
        WHEN 'CLP' THEN 'Legislação Participativa'
        WHEN 'CPD' THEN 'Pessoas com Deficiência'
        WHEN 'CMULHER' THEN 'Direitos da Mulher'
        WHEN 'CIDOSO' THEN 'Pessoa Idosa'
        WHEN 'CPOVOS' THEN 'Amazônia e Povos Originários'
        WHEN 'CINDRE' THEN 'Integração Nacional'
        WHEN 'CCULT' THEN 'Cultura'
        ELSE NULL
    END;

    IF label IS NULL THEN
        label := regexp_replace(trim(coalesce(raw_name, '')), '\s+', ' ', 'g');

        -- Remove official boilerplate that makes labels unnecessarily long.
        label := regexp_replace(label, '^Comiss[aã]o\s+Permanente\s+', '', 'i');
        label := regexp_replace(label, '^Comiss[aã]o\s+(de|da|do|das|dos)\s+', '', 'i');
        label := regexp_replace(label, '^Comiss[aã]o\s+', '', 'i');
        label := regexp_replace(label, '^Especial\s+destinada\s+a\s+', 'Especial: ', 'i');
        label := regexp_replace(label, '^Especial\s+destinada\s+ao\s+', 'Especial: ', 'i');
        label := regexp_replace(label, '^Especial\s+destinada\s+à\s+', 'Especial: ', 'i');

        -- Shorten frequent verbose official names.
        label := regexp_replace(label, 'Agricultura,\s*Pecu[áa]ria,\s*Abastecimento\s+e\s+Desenvolvimento\s+Rural', 'Agricultura', 'i');
        label := regexp_replace(label, 'Fiscaliza[çc][aã]o\s+Financeira\s+e\s+Controle', 'Fiscalização e Controle', 'i');
        label := regexp_replace(label, 'Seguran[çc]a\s+P[úu]blica\s+e\s+Combate\s+ao\s+Crime\s+Organizado', 'Segurança Pública', 'i');
        label := regexp_replace(label, 'Rela[çc][õo]es\s+Exteriores\s+e\s+de\s+Defesa\s+Nacional', 'Relações Exteriores e Defesa', 'i');
        label := regexp_replace(label, 'Trabalho,\s*de\s+Administra[çc][aã]o\s+e\s+Servi[çc]o\s+P[úu]blico', 'Trabalho e Serviço Público', 'i');
        label := regexp_replace(label, 'Defesa\s+dos\s+Direitos\s+das\s+Pessoas\s+com\s+Defici[êe]ncia', 'Pessoas com Deficiência', 'i');
        label := regexp_replace(label, 'Defesa\s+dos\s+Direitos\s+da\s+Mulher', 'Direitos da Mulher', 'i');
        label := regexp_replace(label, 'Defesa\s+dos\s+Direitos\s+da\s+Pessoa\s+Idosa', 'Pessoa Idosa', 'i');
        label := regexp_replace(label, 'Amaz[ôo]nia\s+e\s+dos\s+Povos\s+Origin[áa]rios\s+e\s+Tradicionais', 'Amazônia e Povos Originários', 'i');
        label := regexp_replace(label, 'Integra[çc][aã]o\s+Nacional\s+e\s+Desenvolvimento\s+Regional', 'Integração Nacional', 'i');

        -- Normalize capitalization, then restore common Portuguese connector words.
        label := initcap(lower(label));
        label := replace(label, ' De ', ' de ');
        label := replace(label, ' Da ', ' da ');
        label := replace(label, ' Do ', ' do ');
        label := replace(label, ' Das ', ' das ');
        label := replace(label, ' Dos ', ' dos ');
        label := replace(label, ' E ', ' e ');
        label := replace(label, ' Ao ', ' ao ');
        label := replace(label, ' À ', ' à ');
        label := replace(label, ' A ', ' a ');
        label := replace(label, ' Em ', ' em ');
        label := replace(label, ' Para ', ' para ');
        label := replace(label, ' Com ', ' com ');
    END IF;

    label := nullif(trim(label), '');

    IF label IS NOT NULL AND char_length(label) > 90 THEN
        label := rtrim(left(label, 87)) || '...';
    END IF;

    RETURN label;
END;
$$;

UPDATE core.committees
SET clean_name = core.clean_committee_name(name, acronym)
WHERE clean_name IS NULL OR trim(clean_name) = '';
