import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Refusal Atlas — Political speech across language models',
  description: 'Explore where language models refuse political requests across semantic space, languages and developer jurisdictions.',
  robots: {
    index: false,
    follow: false,
    nocache: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
