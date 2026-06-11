// Computes electron beamspot-relative d0 and extends the Electron NanoAOD
// FlatTable with the result.
//
// Background: in MiniAOD produced with CMSSW_9_4_5, PATElectronProducer
// never assigned the beamspot handle to the beamSpot object before calling
// embedHighLevel(), so dB(BS2D) was computed relative to the origin (0,0,0)
// rather than the actual beamspot. This bug was fixed in 2024 (CMSSW commit
// 50e2d9f). All Run 2 MiniAOD is therefore affected.
//
// Columns produced (all in cm):
//   dxybs / dxybsErr  - gsfTrack()->dxy(beamspot), analytic with tilt

#include "FWCore/Framework/interface/stream/EDProducer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "DataFormats/PatCandidates/interface/Electron.h"
#include "DataFormats/BeamSpot/interface/BeamSpot.h"
#include "DataFormats/NanoAOD/interface/FlatTable.h"

class ElectronDxyBSProducer : public edm::stream::EDProducer<> {
public:
    explicit ElectronDxyBSProducer(const edm::ParameterSet&);
    void produce(edm::Event&, const edm::EventSetup&) override;

private:
    edm::EDGetTokenT<std::vector<pat::Electron>> electronToken_;
    edm::EDGetTokenT<reco::BeamSpot>             beamSpotToken_;
};

ElectronDxyBSProducer::ElectronDxyBSProducer(const edm::ParameterSet& iConfig)
    : electronToken_(consumes<std::vector<pat::Electron>>(
          iConfig.getParameter<edm::InputTag>("electrons"))),
      beamSpotToken_(consumes<reco::BeamSpot>(
          iConfig.getParameter<edm::InputTag>("beamSpot")))
{
    produces<nanoaod::FlatTable>();
}

void ElectronDxyBSProducer::produce(edm::Event& iEvent, const edm::EventSetup& iSetup) {
    edm::Handle<std::vector<pat::Electron>> electrons;
    iEvent.getByToken(electronToken_, electrons);

    edm::Handle<reco::BeamSpot> beamSpotHandle;
    iEvent.getByToken(beamSpotToken_, beamSpotHandle);
    const reco::BeamSpot& bs = *beamSpotHandle;

    const size_t n = electrons->size();
    std::vector<float> dxybs(n), dxybsErr(n);

    for (size_t i = 0; i < n; ++i) {
        auto trk = (*electrons)[i].gsfTrack();
        if (trk.isNonnull()) {
            dxybs[i]    = trk->dxy(bs);
#ifdef CMSSW_LEGACY_NANO_API
            dxybsErr[i] = trk->dxyError();
#else
            dxybsErr[i] = trk->dxyError(bs);
#endif
        } else {
            dxybs[i]    = -999.f;
            dxybsErr[i] = -999.f;
        }
    }

    auto table = std::make_unique<nanoaod::FlatTable>(n, "Electron", false, true);
#ifdef CMSSW_LEGACY_NANO_API
    table->addColumn<float>("dxybs",    dxybs,
        "dxy wrt beamspot from gsfTrack()->dxy(beamspot), includes tilt [cm]",
        nanoaod::FlatTable::FloatColumn, 10);
    table->addColumn<float>("dxybsErr", dxybsErr,
        "dxybs uncertainty [cm]",
        nanoaod::FlatTable::FloatColumn, 6);
#else
    table->addColumn<float>("dxybs",    dxybs,
        "dxy wrt beamspot from gsfTrack()->dxy(beamspot), includes tilt [cm]", 10);
    table->addColumn<float>("dxybsErr", dxybsErr,
        "dxybs uncertainty [cm]", 6);
#endif
    iEvent.put(std::move(table));
}

DEFINE_FWK_MODULE(ElectronDxyBSProducer);
