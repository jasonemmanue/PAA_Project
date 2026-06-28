"use client";

import { useEffect, useState } from "react";

import type { NiveauAcces } from "@/contexts/AuthContext";

const CLE_MDP_LECTURE = "paa_mdp_lecture";
const CLE_MDP_ECRITURE = "paa_mdp_ecriture";
const MDP_LECTURE_DEFAUT = "readhackatonia";
const MDP_ECRITURE_DEFAUT = "readwritehackatonia";

function getMdpLecture(): string {
  if (typeof window === "undefined") return MDP_LECTURE_DEFAUT;
  return localStorage.getItem(CLE_MDP_LECTURE) ?? MDP_LECTURE_DEFAUT;
}

function getMdpEcriture(): string {
  if (typeof window === "undefined") return MDP_ECRITURE_DEFAUT;
  return localStorage.getItem(CLE_MDP_ECRITURE) ?? MDP_ECRITURE_DEFAUT;
}

interface Props {
  onAuthentifie: (niveau: NiveauAcces) => void;
}

export function PasswordGate({ onAuthentifie }: Props) {
  const [motDePasse, setMotDePasse] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [modifierMdp, setModifierMdp] = useState(false);
  const [typeChangement, setTypeChangement] = useState<"lecture" | "ecriture">("lecture");
  const [ancienMdp, setAncienMdp] = useState("");
  const [nouveauMdp, setNouveauMdp] = useState("");
  const [messageSucces, setMessageSucces] = useState<string | null>(null);
  const [montre, setMontre] = useState(false);

  // Léger fondu d'apparition
  useEffect(() => {
    const t = setTimeout(() => setMontre(true), 50);
    return () => clearTimeout(t);
  }, []);

  function valider() {
    const mdpL = getMdpLecture();
    const mdpE = getMdpEcriture();
    if (motDePasse === mdpE) {
      onAuthentifie("ecriture");
    } else if (motDePasse === mdpL) {
      onAuthentifie("lecture");
    } else {
      setErreur("Mot de passe incorrect. Veuillez réessayer.");
      setMotDePasse("");
    }
  }

  function changerMotDePasse() {
    const mdpActuel =
      typeChangement === "lecture" ? getMdpLecture() : getMdpEcriture();
    if (ancienMdp !== mdpActuel) {
      setErreur("Ancien mot de passe incorrect.");
      return;
    }
    if (nouveauMdp.length < 6) {
      setErreur("Le nouveau mot de passe doit comporter au moins 6 caractères.");
      return;
    }
    const cle =
      typeChangement === "lecture" ? CLE_MDP_LECTURE : CLE_MDP_ECRITURE;
    localStorage.setItem(cle, nouveauMdp);
    setMessageSucces(
      `Mot de passe ${typeChangement === "lecture" ? "lecture" : "lecture/écriture"} mis à jour.`,
    );
    setAncienMdp("");
    setNouveauMdp("");
    setErreur(null);
  }

  const inputCls: React.CSSProperties = {
    width: "100%",
    padding: "0.625rem 0.75rem",
    borderRadius: "0.5rem",
    border: "1px solid rgba(255,255,255,0.18)",
    background: "rgba(255,255,255,0.07)",
    color: "white",
    fontSize: "1rem",
    boxSizing: "border-box" as const,
    outline: "none",
  };

  const btnPrimaire: React.CSSProperties = {
    width: "100%",
    padding: "0.75rem",
    background: "#1565C8",
    color: "white",
    border: "none",
    borderRadius: "0.5rem",
    fontSize: "1rem",
    fontWeight: 600,
    cursor: "pointer",
    marginBottom: "0.625rem",
  };

  const btnSecondaire: React.CSSProperties = {
    width: "100%",
    padding: "0.5rem",
    background: "transparent",
    color: "#64748b",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: "0.5rem",
    fontSize: "0.875rem",
    cursor: "pointer",
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 10000,
        background: "#070F1E",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "1rem",
        transition: "opacity 0.4s",
        opacity: montre ? 1 : 0,
      }}
    >
      {/* Fond décoratif */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse at 50% 0%, rgba(21,101,200,0.18) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />

      <div
        style={{
          position: "relative",
          width: "100%",
          maxWidth: "400px",
          background: "rgba(255,255,255,0.05)",
          borderRadius: "1rem",
          padding: "2rem",
          border: "1px solid rgba(255,255,255,0.1)",
          backdropFilter: "blur(12px)",
        }}
      >
        {/* Logo / titre */}
        <div style={{ textAlign: "center", marginBottom: "1.75rem" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 56,
              height: 56,
              borderRadius: "50%",
              background: "rgba(21,101,200,0.25)",
              marginBottom: "0.75rem",
            }}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="#4CC9F0"
              width={28}
              height={28}
            >
              <path
                fillRule="evenodd"
                d="M12 1.5a5.25 5.25 0 0 0-5.25 5.25v3a3 3 0 0 0-3 3v6.75a3 3 0 0 0 3 3h10.5a3 3 0 0 0 3-3v-6.75a3 3 0 0 0-3-3v-3c0-2.9-2.35-5.25-5.25-5.25Zm3.75 8.25v-3a3.75 3.75 0 1 0-7.5 0v3h7.5Z"
                clipRule="evenodd"
              />
            </svg>
          </div>
          <h1 style={{ color: "#4CC9F0", fontSize: "1.5rem", fontWeight: 700, margin: 0 }}>
            PAA-Traverse
          </h1>
          <p style={{ color: "#64748b", fontSize: "0.8rem", margin: "0.25rem 0 0" }}>
            Port Autonome d&apos;Abidjan — Team HACKATONIA
          </p>
        </div>

        {!modifierMdp ? (
          <>
            <label
              style={{
                color: "#94a3b8",
                fontSize: "0.8rem",
                display: "block",
                marginBottom: "0.375rem",
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              Mot de passe d&apos;accès
            </label>
            <input
              type="password"
              value={motDePasse}
              onChange={(e) => {
                setMotDePasse(e.target.value);
                setErreur(null);
              }}
              onKeyDown={(e) => e.key === "Enter" && valider()}
              style={{ ...inputCls, marginBottom: "0.75rem" }}
              placeholder="••••••••••••"
              autoFocus
            />
            {erreur && (
              <p
                style={{
                  color: "#f87171",
                  fontSize: "0.8rem",
                  marginBottom: "0.75rem",
                }}
              >
                {erreur}
              </p>
            )}
            <button onClick={valider} style={btnPrimaire}>
              Accéder →
            </button>
            <button
              onClick={() => {
                setModifierMdp(true);
                setErreur(null);
                setMessageSucces(null);
              }}
              style={btnSecondaire}
            >
              Modifier un mot de passe
            </button>

            {/* Légende des niveaux */}
            <div
              style={{
                marginTop: "1.5rem",
                borderTop: "1px solid rgba(255,255,255,0.07)",
                paddingTop: "1rem",
              }}
            >
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.375rem",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: "#60a5fa",
                      flexShrink: 0,
                    }}
                  />
                  <span style={{ color: "#475569", fontSize: "0.75rem" }}>
                    <strong style={{ color: "#94a3b8" }}>Lecture</strong> — consultation uniquement
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: "#34d399",
                      flexShrink: 0,
                    }}
                  />
                  <span style={{ color: "#475569", fontSize: "0.75rem" }}>
                    <strong style={{ color: "#94a3b8" }}>Lecture/Écriture</strong> — imports, exports, administration
                  </span>
                </div>
              </div>
            </div>
          </>
        ) : (
          <>
            <p style={{ color: "#94a3b8", fontSize: "0.8rem", marginBottom: "0.75rem" }}>
              Modifier le mot de passe :
            </p>

            {/* Sélecteur type */}
            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
              {(["lecture", "ecriture"] as const).map((type) => (
                <button
                  key={type}
                  onClick={() => setTypeChangement(type)}
                  style={{
                    flex: 1,
                    padding: "0.5rem",
                    borderRadius: "0.375rem",
                    border: "none",
                    background:
                      typeChangement === type
                        ? "#1565C8"
                        : "rgba(255,255,255,0.07)",
                    color: typeChangement === type ? "white" : "#94a3b8",
                    cursor: "pointer",
                    fontSize: "0.8rem",
                    fontWeight: typeChangement === type ? 600 : 400,
                  }}
                >
                  {type === "lecture" ? "Lecture" : "Lecture/Écriture"}
                </button>
              ))}
            </div>

            <input
              type="password"
              value={ancienMdp}
              onChange={(e) => {
                setAncienMdp(e.target.value);
                setErreur(null);
              }}
              placeholder="Ancien mot de passe"
              style={{ ...inputCls, marginBottom: "0.5rem" }}
            />
            <input
              type="password"
              value={nouveauMdp}
              onChange={(e) => {
                setNouveauMdp(e.target.value);
                setErreur(null);
              }}
              placeholder="Nouveau mot de passe (min. 6 car.)"
              style={{ ...inputCls, marginBottom: "0.75rem" }}
            />

            {erreur && (
              <p style={{ color: "#f87171", fontSize: "0.8rem", marginBottom: "0.5rem" }}>
                {erreur}
              </p>
            )}
            {messageSucces && (
              <p style={{ color: "#4ade80", fontSize: "0.8rem", marginBottom: "0.5rem" }}>
                {messageSucces}
              </p>
            )}

            <button onClick={changerMotDePasse} style={btnPrimaire}>
              Mettre à jour
            </button>
            <button
              onClick={() => {
                setModifierMdp(false);
                setErreur(null);
                setMessageSucces(null);
                setAncienMdp("");
                setNouveauMdp("");
              }}
              style={btnSecondaire}
            >
              ← Retour
            </button>
          </>
        )}
      </div>
    </div>
  );
}
