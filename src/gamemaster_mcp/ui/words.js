/* Gamemaster MCP pages: their words in English and French, picked from the
 * browser's language. t("key") also passes through an unknown key, so a
 * server message without a translation still shows. */
"use strict";

const I18N = (() => {
  const FRENCH = (navigator.language || "").toLowerCase().startsWith("fr");
  const WORDS = {
    round: ["Round", "Round"], turn: ["turn", "tour"], hp: ["HP", "PV"], ac: ["AC", "CA"],
    total: ["Total", "Total"], advantage: ["Advantage", "Avantage"],
    disadvantage: ["Disadvantage", "Désavantage"], waiting: ["Rolling…", "Lancer…"],
    noCombat: ["No combat running.", "Aucun combat en cours."],
    defeated: ["Overcome", "Vaincus"], xp: ["XP", "XP"], session: ["Session", "Session"],
    funds: ["Funds", "Bourse"], quests: ["Active quests", "Quêtes en cours"],
    noQuest: ["No active quest.", "Aucune quête en cours."], inCombat: ["In combat", "En combat"],
    party: ["Party", "Groupe"], noParty: ["No character yet.", "Aucun personnage."],
    slots: ["Spell slots", "Emplacements de sorts"], spells: ["Spells", "Sorts"],
    inventory: ["Inventory", "Inventaire"], cantrip: ["Cantrip", "Tour de magie"],
    level: ["Level", "Niveau"], prepared: ["prepared", "préparé"],
    proficiency: ["Proficiency", "Maîtrise"], inspiration: ["Inspiration", "Inspiration"],
    deathSaves: ["Death saves", "Jets contre la mort"], exhaustion: ["Exhaustion", "Épuisement"],
    temp: ["temp", "temp"], unknown: ["unknown", "inconnu"], nextLevel: ["next level", "niveau suivant"],
    turnOf: ["{name}'s turn", "Tour de {name}"], lvl: ["Lvl", "Niv."],
    str: ["STR", "FOR"], dex: ["DEX", "DEX"], con: ["CON", "CON"], int: ["INT", "INT"],
    wis: ["WIS", "SAG"], cha: ["CHA", "CHA"],
    blinded: ["blinded", "aveuglé"], charmed: ["charmed", "charmé"], deafened: ["deafened", "assourdi"],
    frightened: ["frightened", "effrayé"], grappled: ["grappled", "agrippé"],
    incapacitated: ["incapacitated", "neutralisé"], invisible: ["invisible", "invisible"],
    paralyzed: ["paralyzed", "paralysé"], petrified: ["petrified", "pétrifié"],
    poisoned: ["poisoned", "empoisonné"], prone: ["prone", "à terre"],
    restrained: ["restrained", "entravé"], stunned: ["stunned", "étourdi"],
    unconscious: ["unconscious", "inconscient"],
    // How hurt a monster looks to the players.
    unhurt: ["unhurt", "indemne"], hurt: ["hurt", "blessé"], bloodied: ["bloodied", "en sang"],
    down: ["down", "hors de combat"],
    speed: ["Speed", "Vitesse"],
    // The table.
    theTable: ["🪑 The table", "🪑 La table"], noCharacter: ["no character yet", "pas encore de personnage"],
    nobodySeated: ["Nobody seated yet: the game master asks who is playing.",
      "Personne n'est encore installé : le maître du jeu demande qui joue."],
    absentees: ["Absent", "Absents"], knownPlayers: ["Known players", "Joueurs connus"],
    noPlayer: ["No player", "Sans joueur"], away: ["absent", "absent"], unplayed: ["no player", "sans joueur"],
    // Web pages.
    yourTurn: ["Your turn!", "À toi de jouer !"], journal: ["Adventure log", "Journal"],
    noEvent: ["Nothing logged yet.", "Rien de noté pour l'instant."], from: ["from {name}", "confiée par {name}"],
    players: ["Players", "Joueurs"], showCodes: ["Join codes", "Codes joueurs"], hideCodes: ["Hide", "Masquer"],
    scanToJoin: ["Scan your character's code to follow it on your phone.",
      "Scanne le code de ton personnage pour le suivre sur ton téléphone."],
    unreachable: ["Phones cannot reach this server: start it with GAMEMASTER_WEB_HOST=0.0.0.0.",
      "Les téléphones ne peuvent pas joindre ce serveur : lance-le avec GAMEMASTER_WEB_HOST=0.0.0.0."],
    noCampaign: ["No active campaign.", "Aucune campagne active."],
    unknownLink: ["This link no longer matches a character of the active campaign.",
      "Ce lien ne correspond plus à un personnage de la campagne active."],
    offline: ["Connection lost, reconnecting…", "Connexion perdue, reconnexion…"],
    // Adventure log entries.
    combat: ["combat", "combat"], roleplay: ["roleplay", "interprétation"], exploration: ["exploration", "exploration"],
    quest: ["quest", "quête"], character: ["character", "personnage"], world: ["world", "monde"],
    // Backstage.
    backstage: ["Backstage", "Régie"], encounters: ["Planned encounters", "Rencontres prévues"],
    noEncounter: ["Nothing planned.", "Rien de prévu."], npcs: ["NPCs", "PNJ"], noNpc: ["No NPC yet.", "Aucun PNJ."],
    allQuests: ["Quests", "Quêtes"], bestiary: ["Bestiary", "Bestiaire"], noMonster: ["Empty.", "Vide."],
    notes: ["Notes", "Notes"], reward: ["Reward", "Récompense"], secret: ["Secret", "Secret"],
    planned: ["planned", "prévue"], running: ["running", "en cours"],
    trivial: ["trivial", "triviale"], easy: ["easy", "facile"], medium: ["medium", "moyenne"],
    hard: ["hard", "difficile"], deadly: ["deadly", "mortelle"],
    friendly: ["friendly", "amical"], neutral: ["neutral", "neutre"], hostile: ["hostile", "hostile"],
    active: ["active", "en cours"], completed: ["completed", "accomplie"], failed: ["failed", "échouée"],
    on_hold: ["on hold", "en pause"],
  };

  function t(key, values) {
    const text = (WORDS[key] ? WORDS[key][FRENCH ? 1 : 0] : String(key)).replace(/\{(\w+)\}/g, (_, name) =>
      values && values[name] !== undefined ? values[name] : "");
    // French elision: "Tour de Élodie" -> "Tour d'Élodie".
    return FRENCH ? text.replace(/\bde ([aeiouyàâéèêëîïôûü])/gi, "d'$1") : text;
  }

  /** A distance as the players' books give it: feet, or metres in French (5 ft = 1.5 m). */
  const distance = (feet) => (FRENCH ? `${(feet * 0.3).toLocaleString("fr")} m` : `${feet} ft`);

  return { t, distance, FRENCH };
})();
