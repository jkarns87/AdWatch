import { redirect } from "next/navigation";

/** Interim root. Becomes the dashboard in sub-project D; until then the list
 *  lives at /watchlists and this keeps "/" from being a dead route. */
export default function Home() {
  redirect("/watchlists");
}
