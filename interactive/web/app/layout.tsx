import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Refusal Observatory',
  description: 'Explore where language models refuse across semantic space.',
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
