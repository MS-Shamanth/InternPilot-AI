import { Link } from 'react-router-dom';

import { PageHeader } from '../components/layout/PageHeader';
import { NOT_FOUND_TITLE } from '../components/layout/navigation';
import { buttonClasses } from '../components/ui/buttonStyles';

export default function NotFoundPage() {
  return (
    <>
      <PageHeader
        title={NOT_FOUND_TITLE}
        description="The page you are looking for does not exist or has moved."
      />
      <Link to="/dashboard" className={buttonClasses()}>
        Back to Dashboard
      </Link>
    </>
  );
}
