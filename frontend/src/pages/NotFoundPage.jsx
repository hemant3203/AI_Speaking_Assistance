/** 404: a wrong turn backstage. */
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/States';
import { useDocumentTitle } from '../components/ui/PageHeader';
import { DoorOpen } from 'lucide-react';

export default function NotFoundPage() {
  useDocumentTitle('Page not found');
  return (
    <EmptyState icon={DoorOpen} title="Wrong stage door" action={<Button to="/">Back to home</Button>}>
      There's nothing at this address. Let's get you back under the lights.
    </EmptyState>
  );
}
