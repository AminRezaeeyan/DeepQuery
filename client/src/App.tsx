import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/auth";
import { ThemeProvider } from "./lib/theme";
import { ToastProvider } from "./components/Toast";
import { LoginPage, RegisterPage } from "./pages/AuthPages";
import { PlansPage } from "./pages/PlansPage";
import { PaymentResultPage } from "./pages/PaymentResultPage";
import { Workspace } from "./features/chat/Workspace";

function Private({ children }: { children: ReactNode }) {
  const { isAuthed } = useAuth();
  return isAuthed ? children : <Navigate to="/login" replace />;
}

function Public({ children }: { children: ReactNode }) {
  const { isAuthed } = useAuth();
  return isAuthed ? <Navigate to="/" replace /> : children;
}

export function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<Public><LoginPage /></Public>} />
              <Route path="/register" element={<Public><RegisterPage /></Public>} />
              <Route path="/plans" element={<Private><PlansPage /></Private>} />
              {/* Not private: the sign-in may have expired while the user was paying. */}
              <Route path="/payment/result" element={<PaymentResultPage />} />
              <Route path="/" element={<Private><Workspace /></Private>} />
              <Route path="/c/:chatId" element={<Private><Workspace /></Private>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}
