// La taille du texte vit ici, et **seulement** ici : 16px sur mobile, 14px à
// partir de `md`. Sous 16px, Mobile Safari zoome le viewport dès qu'un champ
// prend le focus, et en PWA installée plus aucun geste ne ramène à l'échelle.
// Un champ qui pose sa propre taille la repasse sous la barre sans qu'on le
// voie en revue — d'où `field-font-size.test.ts`.
export const fieldBase =
  "flex w-full rounded-md border border-input bg-background px-3 py-2 text-base md:text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 touch-manipulation"
