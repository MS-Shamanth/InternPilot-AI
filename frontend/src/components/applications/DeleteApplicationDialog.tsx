import { useRef } from 'react';
import type { Application } from '../../types/api';
import { Button } from '../ui/Button';
import { Dialog } from '../ui/Dialog';

interface DeleteApplicationDialogProps {
  application: Application;
  open: boolean;
  isDeleting: boolean;
  onCancel: () => void;
  onConfirm: (application: Application) => void;
}

/** Confirms removing an application (R5.8); Cancel has focus so Enter never deletes by accident. */
export function DeleteApplicationDialog({
  application,
  open,
  isDeleting,
  onCancel,
  onConfirm,
}: DeleteApplicationDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const { job } = application;
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      title="Delete application?"
      description={`This removes “${job.title}” at ${job.company} from your tracker. The job stays in your job list.`}
      initialFocusRef={cancelRef}
      footer={
        <>
          <Button ref={cancelRef} variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant="danger"
            isLoading={isDeleting}
            onClick={() => {
              onConfirm(application);
            }}
          >
            Delete application
          </Button>
        </>
      }
    />
  );
}
