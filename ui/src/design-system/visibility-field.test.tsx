import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import i18n from 'i18next';
import { I18nextProvider, initReactI18next } from 'react-i18next';
import { beforeAll, describe, expect, it, vi } from 'vitest';

import fr from '@/locales/fr/translation.json';

import { VisibilityField } from './visibility-field';

/**
 * Les deux états sont nommés, et l'actif se voit sans rien ouvrir.
 *
 * La confidentialité avait deux dessins pour une même notion — une case à cocher
 * sur les tâches, un menu déroulant sur les briefings — et **aucun** sur les deux
 * autres modèles qui portent le drapeau. Ce qui est testé ici n'est pas
 * l'apparence, c'est la propriété qui a motivé le remplacement : **une case à
 * cocher ne nomme qu'un seul état.** Décochée, elle laisse deviner ce qu'elle
 * veut dire ; et sur un réglage dont l'erreur se paie en « tout le foyer a vu mon
 * cadeau », deviner ne suffit pas.
 *
 * Le test porte donc sur les **noms accessibles** et sur l'exclusion mutuelle, pas
 * sur des classes CSS : un `bg-primary/10` peut changer au prochain thème sans que
 * rien ne se casse, tandis qu'un état qui cesse d'être nommé, si.
 *
 * ⚠️ Le catalogue français est chargé pour de vrai. Sans lui, `t('privacy.shared')`
 * renvoie la **clé brute** — et « privacy.shared » contient « priv », donc une
 * recherche par nom accessible trouverait *les deux* boutons et le test passerait
 * ou échouerait pour la mauvaise raison. Un test qui ne peut pas distinguer les
 * deux états ne prouve rien sur un composant dont c'est justement la fonction.
 */
beforeAll(async () => {
  await i18n.use(initReactI18next).init({
    lng: 'fr',
    resources: { fr: { translation: fr } },
    interpolation: { escapeValue: false },
  });
});

function renderField(props: React.ComponentProps<typeof VisibilityField>) {
  return render(
    <I18nextProvider i18n={i18n}>
      <VisibilityField {...props} />
    </I18nextProvider>,
  );
}

describe('VisibilityField', () => {
  it('nomme les deux états, pas seulement celui qui est actif', () => {
    renderField({ id: 'v', value: false, onChange: () => {} });

    const radios = screen.getAllByRole('radio');
    expect(radios).toHaveLength(2);

    const names = radios.map((radio) => radio.getAttribute('id'));
    expect(names).toEqual(['v-shared', 'v-private']);
  });

  it('reflète l’état courant sur le bon bouton', () => {
    const { rerender } = renderField({ id: 'v', value: false, onChange: () => {} });
    expect((screen.getByRole('radio', { name: /partag|shared/i }) as HTMLInputElement).checked).toBe(true);

    rerender(
      <I18nextProvider i18n={i18n}>
        <VisibilityField id="v" value onChange={() => {}} />
      </I18nextProvider>,
    );
    expect((screen.getByRole('radio', { name: /priv/i }) as HTMLInputElement).checked).toBe(true);
  });

  it('rend les deux options mutuellement exclusives', () => {
    renderField({ id: 'v', value: false, onChange: () => {} });
    const [shared, priv] = screen.getAllByRole('radio');
    // Même attribut `name` : c'est le navigateur qui garantit l'exclusion et la
    // navigation au clavier — on ne la réimplémente pas.
    expect(shared.getAttribute('name')).toBe(priv.getAttribute('name'));
  });

  it('annonce true pour privé et false pour partagé', async () => {
    const onChange = vi.fn();
    renderField({ id: 'v', value: false, onChange });

    await userEvent.click(screen.getByRole('radio', { name: /priv/i }));
    expect(onChange).toHaveBeenCalledWith(true);

    onChange.mockClear();
    renderField({ id: 'w', value: true, onChange });
    await userEvent.click(screen.getAllByRole('radio', { name: /partag|shared/i })[1]);
    expect(onChange).toHaveBeenCalledWith(false);
  });

  it('n’affiche la conséquence propre à l’écran que quand elle s’applique', () => {
    const hint = 'Une tâche privée ne peut pas être assignée';

    const { rerender } = renderField({
      id: 'v', value: false, onChange: () => {}, privateHint: hint,
    });
    expect(screen.queryByText(hint)).toBeNull();

    rerender(
      <I18nextProvider i18n={i18n}>
        <VisibilityField id="v" value onChange={() => {}} privateHint={hint} />
      </I18nextProvider>,
    );
    expect(screen.getByText(hint)).toBeTruthy();
  });
});
