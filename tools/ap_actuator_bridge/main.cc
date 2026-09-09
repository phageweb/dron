// Bridge ArduPilotPlugin's per-joint COMMAND output to a MulticopterMotorModel.
//
// ArduPilotPlugin's <control type="COMMAND"> publishes one gz.msgs.Double per
// rotor. MulticopterMotorModel instead reads a single gz.msgs.Actuators array
// indexed by <actuator_number>. This process is the adapter between them, which
// lets the rotors be driven without the plugin's joint force PID - a loop that
// is unusable at the inertia of a 3 in propeller.
//
// Rotor speeds are published as magnitudes; the motor model applies the sign
// from its own <turningDirection>.

#include <atomic>
#include <chrono>
#include <csignal>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

#include <gz/msgs/actuators.pb.h>
#include <gz/msgs/double.pb.h>
#include <gz/transport/Node.hh>

namespace
{
constexpr int kRotorCount = 4;
std::atomic<bool> g_stop{false};
std::atomic<double> g_speed[kRotorCount];

void OnSignal(int)
{
  g_stop = true;
}
}  // namespace

int main(int argc, char **argv)
{
  std::string model = "openipc_cinewhoop";
  std::string command_topic;
  double rate_hz = 250.0;

  for (int i = 1; i < argc; ++i)
  {
    const std::string arg = argv[i];
    if (arg == "--model" && i + 1 < argc)
      model = argv[++i];
    else if (arg == "--command-topic" && i + 1 < argc)
      command_topic = argv[++i];
    else if (arg == "--rate" && i + 1 < argc)
      rate_hz = std::stod(argv[++i]);
    else
    {
      std::cerr << "usage: ap_actuator_bridge [--model NAME] "
                   "[--command-topic TOPIC] [--rate HZ]\n";
      return 2;
    }
  }

  if (command_topic.empty())
    command_topic = "/" + model + "/command/motor_speed";

  for (int i = 0; i < kRotorCount; ++i)
    g_speed[i] = 0.0;

  gz::transport::Node node;

  for (int i = 0; i < kRotorCount; ++i)
  {
    const std::string topic =
        "/model/" + model + "/joint/rotor_" + std::to_string(i) + "_joint/cmd";
    // Each rotor arrives on its own topic; store the latest magnitude.
    const bool ok = node.Subscribe<gz::msgs::Double>(
        topic, [i](const gz::msgs::Double &msg)
        {
          g_speed[i] = std::abs(msg.data());
        });
    if (!ok)
    {
      std::cerr << "failed to subscribe to " << topic << "\n";
      return 1;
    }
    std::cout << "subscribed " << topic << "\n";
  }

  auto pub = node.Advertise<gz::msgs::Actuators>(command_topic);
  if (!pub)
  {
    std::cerr << "failed to advertise " << command_topic << "\n";
    return 1;
  }
  std::cout << "publishing " << command_topic << " at " << rate_hz << " Hz\n";

  std::signal(SIGINT, OnSignal);
  std::signal(SIGTERM, OnSignal);

  const auto period =
      std::chrono::microseconds(static_cast<long>(1e6 / rate_hz));
  gz::msgs::Actuators msg;
  msg.mutable_velocity()->Resize(kRotorCount, 0.0);

  while (!g_stop)
  {
    for (int i = 0; i < kRotorCount; ++i)
      msg.set_velocity(i, g_speed[i]);
    pub.Publish(msg);
    std::this_thread::sleep_for(period);
  }

  std::cout << "ap_actuator_bridge stopping\n";
  return 0;
}
