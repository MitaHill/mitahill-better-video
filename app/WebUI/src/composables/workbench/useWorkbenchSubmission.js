import { resolveSubmitter } from "./submission";

export const useWorkbenchSubmission = ({
  activeCategory,
  loading,
  submitError,
  submitWarnings,
  enhanceForm,
  convertForm,
  transcribeForm,
  taskIds,
  setStatusQuery,
  fetchStatus,
  joinRoom,
  parseJsonSafe,
  enforceCategory,
  prepareTranscribeUploadFiles,
}) => {
  const submissionContext = {
    enforceCategory,
    enhanceForm,
    convertForm,
    transcribeForm,
      taskIds,
    setStatusQuery,
    submitWarnings,
    joinRoom,
    fetchStatus,
    parseJsonSafe,
    prepareTranscribeUploadFiles,
  };

  const submitTask = async () => {
    submitError.value = "";
    submitWarnings.value = "";
    loading.submit = true;
    try {
      const submitter = resolveSubmitter(activeCategory.value);
      await submitter(submissionContext);
    } catch (error) {
      submitError.value = error.message;
    } finally {
      loading.submit = false;
    }
  };

  return {
    submitTask,
  };
};
