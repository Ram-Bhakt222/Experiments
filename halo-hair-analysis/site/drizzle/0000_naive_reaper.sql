CREATE TABLE `halo_analyses` (
	`id` text PRIMARY KEY NOT NULL,
	`created_at` integer NOT NULL,
	`analysis_json` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `halo_leads` (
	`id` text PRIMARY KEY NOT NULL,
	`created_at` integer NOT NULL,
	`email` text NOT NULL,
	`name` text DEFAULT '' NOT NULL,
	`opt_in` integer DEFAULT false NOT NULL,
	`style_identity` text DEFAULT '' NOT NULL,
	`vibe` text DEFAULT '' NOT NULL,
	`hair_type` text DEFAULT '' NOT NULL,
	`color_season` text DEFAULT '' NOT NULL
);
