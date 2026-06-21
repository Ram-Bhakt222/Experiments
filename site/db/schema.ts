import { index, integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const analyses = sqliteTable("halo_analyses", {
  id: text("id").primaryKey(),
  createdAt: integer("created_at", { mode: "timestamp_ms" }).notNull(),
  analysisJson: text("analysis_json", { mode: "json" }).notNull(),
});

export const leads = sqliteTable(
  "halo_leads",
  {
    id: text("id").primaryKey(),
    createdAt: integer("created_at", { mode: "timestamp_ms" }).notNull(),
    email: text("email").notNull(),
    name: text("name").notNull().default(""),
    optIn: integer("opt_in", { mode: "boolean" }).notNull().default(false),
    styleIdentity: text("style_identity").notNull().default(""),
    vibe: text("vibe").notNull().default(""),
    hairType: text("hair_type").notNull().default(""),
    colorSeason: text("color_season").notNull().default(""),
  },
  (table) => [index("halo_leads_email_idx").on(table.email)],
);
