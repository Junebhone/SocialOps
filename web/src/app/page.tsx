import { redirect } from "next/navigation";

export default function Home() {
  // The Inbox is the product's front door.
  redirect("/inbox");
}
