import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './styles.css'
import Layout from './components/Layout'
import Home from './pages/Home'
import ReportHelp from './pages/ReportHelp'
import Track from './pages/Track'
import Status from './pages/Status'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import SignIn from './pages/SignIn'
import MyRequests from './pages/MyRequests'
import SmsPage from './pages/SmsPage'
import Driver from './pages/Driver'
import LoginChooser from './pages/LoginChooser'
import DriverLogin from './pages/DriverLogin'

createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/report" element={<ReportHelp />} />
        <Route path="/track" element={<Track />} />
        <Route path="/status" element={<Status />} />
        <Route path="/login" element={<LoginChooser />} />
        <Route path="/login/citizen" element={<SignIn />} />
        <Route path="/login/officer" element={<Login />} />
        <Route path="/login/driver" element={<DriverLogin />} />
        <Route path="/signin" element={<Navigate to="/login/citizen" replace />} />
        <Route path="/my-requests" element={<MyRequests />} />
        <Route path="/sms" element={<SmsPage />} />
        <Route path="/driver" element={<Driver />} />
      </Route>
      <Route path="/control-room" element={<Dashboard />} />
    </Routes>
  </BrowserRouter>,
)
